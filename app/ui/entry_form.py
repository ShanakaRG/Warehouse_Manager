"""The incoming / outgoing entry form (also reused inside the Edit dialog)."""
from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import ttk
from typing import Callable

from ..database import EPS, IN, Database, ValidationError
from ..utils import fmt_qty
from . import theme
from .dialogs import MaterialDialog
from .theme import FONTS
from .widgets import AutoCombobox, DateField, Modal, QtyField, confirm, warn


class ExtraFieldRow(ttk.Frame):
    """One user-defined 'field name : value' pair, e.g. 'Batch no : B-1024'."""

    def __init__(self, parent, known_names: list[str], on_remove: Callable, key: str = "",
                 value: str = ""):
        super().__init__(parent, style="Card.TFrame")
        self.key = AutoCombobox(self, width=18)
        self.key.set_choices(known_names)
        self.key.set(key)
        self.value = ttk.Entry(self)
        self.value.insert(0, value)
        self.key.pack(side="left")
        self.value.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(self, text="Remove", style="Danger.TButton",
                   command=lambda: on_remove(self)).pack(side="left")

    def pair(self) -> tuple[str, str]:
        return self.key.get().strip(), self.value.get().strip()


class EntryForm(ttk.Frame):
    def __init__(self, parent, db: Database, txn_type: str, txn: dict | None = None,
                 on_saved: Callable[[int], None] | None = None,
                 on_cancel: Callable[[], None] | None = None):
        super().__init__(parent, style="Card.TFrame")
        self.on_cancel = on_cancel
        self.db = db
        self.txn_type = txn_type
        self.txn = txn                    # set when editing an existing entry
        self.is_in = txn_type == IN
        self.on_saved = on_saved
        self._materials: dict[str, dict] = {}
        self._extra_rows: list[ExtraFieldRow] = []
        self._known_fields: list[str] = []
        self._build()
        self.reload_lists()
        if txn:
            self._load(txn)
        else:
            self.clear()

    # ------------------------------------------------------------ layout ---
    def _label(self, row: int, text: str):
        ttk.Label(self, text=text, style="Card.TLabel").grid(
            row=row, column=0, sticky="nw", padx=(0, 16), pady=(10, 0))

    def _hint(self, row: int, text: str):
        ttk.Label(self, text=text, style="CardMuted.TLabel", font=FONTS["small"]).grid(
            row=row, column=1, sticky="w")

    def _build(self):
        is_in = self.is_in
        self.columnconfigure(1, weight=1)
        r = 0

        # Material
        self._label(r, "Material *")
        if is_in:
            self.material = AutoCombobox(self)
        else:
            self.material = ttk.Combobox(self, state="readonly")
        self.material.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        self.material.bind("<<ComboboxSelected>>", lambda _: self._on_material_changed(), add="+")
        self.material.bind("<KeyRelease>", lambda _: self._on_material_changed(), add="+")
        r += 1
        if is_in:
            self._hint(r, "Pick from the list, or type a new name to add a new material.")
        else:
            self.available = ttk.Label(self, text="", style="Available.TLabel")
            self.available.grid(row=r, column=1, sticky="w", pady=(4, 0))
        r += 1

        # Date
        self._label(r, "Date *")
        self.date = DateField(self)
        self.date.grid(row=r, column=1, sticky="w", pady=(6, 0))
        r += 1

        # Quantity
        self._label(r, "Quantity *")
        qty_row = ttk.Frame(self, style="Card.TFrame")
        qty_row.grid(row=r, column=1, sticky="w", pady=(6, 0))
        self.qty = QtyField(qty_row, on_limit=self._show_limit)
        self.qty.pack(side="left")
        self.unit_label = ttk.Label(qty_row, text="", style="CardBold.TLabel")
        self.unit_label.pack(side="left", padx=(8, 12))
        if not is_in:
            self.all_btn = ttk.Button(qty_row, text="Issue all available",
                                      command=lambda: self.qty.set_value(self.qty.maximum or 0))
            self.all_btn.pack(side="left")
        r += 1
        self.limit_label = ttk.Label(self, text="", style="Warning.TLabel")
        self.limit_label.grid(row=r, column=1, sticky="w")
        r += 1

        # Party
        self._label(r, "Supplier *" if is_in else "Issued to *")
        self.party = AutoCombobox(self)
        self.party.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        self.party.bind("<FocusOut>", lambda _: self._autofill_details(), add="+")
        self.party.bind("<<ComboboxSelected>>", lambda _: self._autofill_details(), add="+")
        r += 1
        self._hint(r, "Supplier or company name" if is_in
                   else "Person, department, site or customer")
        r += 1

        self._label(r, "Supplier details" if is_in else "Receiver details")
        self.party_details = ttk.Entry(self)
        self.party_details.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        r += 1
        self._hint(r, "Phone, address, contact person")
        r += 1

        self._label(r, "Reference no.")
        self.ref = ttk.Entry(self)
        self.ref.grid(row=r, column=1, sticky="ew", pady=(6, 0))
        r += 1
        self._hint(r, "Invoice, GRN or delivery note number" if is_in
                   else "Issue note, job or request number")
        r += 1

        self._label(r, "Remarks")
        self.remarks = tk.Text(self, height=3, wrap="word", relief="flat", font=FONTS["base"],
                               background=theme.SURFACE, foreground=theme.TEXT,
                               highlightthickness=1, highlightbackground="#B9C2CC",
                               highlightcolor="#3A6EA5", padx=6, pady=5, insertbackground=theme.TEXT)
        self.remarks.grid(row=r, column=1, sticky="ew", pady=(8, 0))
        self.remarks.bind("<Tab>", lambda e: (e.widget.tk_focusNext().focus_set(), "break")[1])
        r += 1

        # User-defined extra fields
        ttk.Label(self, text="Additional details", style="CardTitle.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(18, 0))
        r += 1
        ttk.Label(self, text="Need to record something else, like a batch number, vehicle number "
                             "or expiry date? Add your own field.",
                  style="CardMuted.TLabel", wraplength=460, justify="left").grid(
            row=r, column=0, columnspan=2, sticky="w")
        r += 1
        self.extra_head = ttk.Frame(self, style="Card.TFrame")
        ttk.Label(self.extra_head, text="Field name", style="CardMuted.TLabel", width=20).pack(side="left")
        ttk.Label(self.extra_head, text="Value", style="CardMuted.TLabel").pack(side="left", padx=6)
        self.extra_head_row = r
        r += 1
        self.extra_box = ttk.Frame(self, style="Card.TFrame")
        self.extra_box.grid(row=r, column=0, columnspan=2, sticky="ew")
        r += 1
        ttk.Button(self, text="+ Add a field", style="CardLink.TButton",
                   command=lambda: self._add_extra_row()).grid(row=r, column=0, columnspan=2,
                                                                sticky="w", pady=(4, 0))
        r += 1

        # Actions
        actions = ttk.Frame(self, style="Card.TFrame")
        actions.grid(row=r, column=0, columnspan=2, sticky="w", pady=(18, 0))
        if self.txn:
            text = "Save changes"
        else:
            text = "Save incoming entry" if is_in else "Save outgoing entry"
        self.save_btn = ttk.Button(actions, text=text, command=self.save,
                                   style="Receive.TButton" if is_in else "Issue.TButton")
        self.save_btn.pack(side="left")
        if self.on_cancel:
            ttk.Button(actions, text="Cancel", command=self.on_cancel).pack(side="left", padx=8)
        elif not self.txn:
            ttk.Button(actions, text="Clear form", command=self.clear).pack(side="left", padx=8)
        r += 1
        self.saved_label = ttk.Label(self, text="", style="Saved.TLabel", wraplength=480,
                                     justify="left")
        self.saved_label.grid(row=r, column=0, columnspan=2, sticky="w", pady=(10, 0))

    # ------------------------------------------------------------ data ---
    def reload_lists(self):
        typed = self.material.get()
        materials = self.db.stock_balance()
        self._materials = {m["name"].lower(): m for m in materials}
        editing_id = self.txn["material_id"] if self.txn else None
        names = [m["name"] for m in materials
                 if self.is_in or m["balance"] > EPS or m["id"] == editing_id]
        if self.is_in:
            self.material.set_choices(names)
            self.material.set(typed)
        else:
            self.material.configure(values=names)
            self.material.set(typed if typed in names else "")
        self.party.set_choices(self.db.party_names(self.txn_type))
        self._known_fields = self.db.extra_field_names()
        self._on_material_changed()

    def _selected_material(self) -> dict | None:
        return self._materials.get(self.material.get().strip().lower())

    def _max_for_outgoing(self, m: dict) -> float:
        available = m["balance"]
        if self.txn and self.txn["material_id"] == m["id"]:
            available += self.txn["quantity"]    # this entry's own quantity counts as available
        return round(available, 3)

    def _on_material_changed(self):
        m = self._selected_material()
        self.unit_label.configure(text=m["unit"] if m else "")
        self.limit_label.configure(text="")
        if self.is_in:
            return
        if not self.material.cget("values"):
            self.available.configure(text="Nothing in stock yet. Record incoming materials first.",
                                     style="Warning.TLabel")
            self._set_out_enabled(False)
            return
        self._set_out_enabled(True)
        if not m:
            self.qty.set_maximum(0)
            self.available.configure(text="Pick a material to see how much you can issue.",
                                     style="CardMuted.TLabel")
            return
        maximum = self._max_for_outgoing(m)
        self.qty.set_maximum(maximum)   # typing a bigger number is refused
        self.available.configure(text=f"Available to issue: {fmt_qty(maximum)} {m['unit']}",
                                 style="Available.TLabel" if maximum > EPS else "Warning.TLabel")

    def _show_limit(self, maximum: float):
        m = self._selected_material()
        unit = m["unit"] if m else ""
        self.limit_label.configure(text=f"You can issue at most {fmt_qty(maximum)} {unit}.")

    def _set_out_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for widget in (self.qty, self.all_btn, self.save_btn):
            widget.configure(state=state)

    def _autofill_details(self):
        if not self.party_details.get().strip() and self.party.get().strip():
            details = self.db.last_party_details(self.txn_type, self.party.get())
            if details:
                self.party_details.insert(0, details)

    def _add_extra_row(self, key: str = "", value: str = ""):
        row = ExtraFieldRow(self.extra_box, self._known_fields, self._remove_extra_row, key, value)
        row.pack(fill="x", pady=2)
        self._extra_rows.append(row)
        self.extra_head.grid(row=self.extra_head_row, column=0, columnspan=2, sticky="w",
                             pady=(8, 0))
        if not key:
            row.key.focus_set()

    def _remove_extra_row(self, row: ExtraFieldRow):
        self._extra_rows.remove(row)
        row.destroy()
        if not self._extra_rows:
            self.extra_head.grid_remove()

    def _extra_values(self) -> dict | None:
        values = {}
        for row in self._extra_rows:
            key, value = row.pair()
            if not key and not value:
                continue
            if not key:
                warn(self, "Field name missing",
                     f"You entered '{value}' under Additional details but no field name.\n\n"
                     "Type a field name, or remove that row.")
                return None
            values[key] = value
        return values

    def clear(self, keep_date: bool = False):
        if not keep_date:
            self.date.set_date(date.today())
        self.material.set("")
        self.qty.set_value(None)
        self.party.set("")
        for widget in (self.party_details, self.ref):
            widget.delete(0, "end")
        self.remarks.delete("1.0", "end")
        for row in list(self._extra_rows):
            self._remove_extra_row(row)
        self._on_material_changed()
        self.material.focus_set()

    def _load(self, t: dict):
        self.material.set(t["material_name"])
        self._on_material_changed()      # sets the maximum first...
        self.qty.set_value(t["quantity"])  # ...so the quantity is accepted
        self.date.set_date(datetime.strptime(t["txn_date"], "%Y-%m-%d").date())
        self.party.set(t["party_name"])
        self.party_details.insert(0, t["party_details"])
        self.ref.insert(0, t["reference_no"])
        self.remarks.insert("1.0", t["remarks"])
        for key, value in t["extra_fields"].items():
            self._add_extra_row(key, value)

    # ------------------------------------------------------------ save ---
    def save(self):
        self.saved_label.configure(text="")
        name = self.material.get().strip()
        if not name:
            warn(self, "Material needed",
                 "Pick a material" + (" or type a new one." if self.is_in else "."))
            self.material.focus_set()
            return
        m = self._selected_material()
        if m is None:
            if not self.is_in:
                warn(self, "Material not in stock", "Pick a material from the list.")
                return
            if not self._create_material(name):
                return
            m = self._selected_material()

        txn_date = self.date.get_date()
        if txn_date is None:
            warn(self, "Date not recognised", "Enter the date as day/month/year, e.g. 25/08/2026, "
                                              "or press Calendar.")
            self.date.entry.focus_set()
            return
        if txn_date > date.today():
            warn(self, "Date in the future", "The date cannot be later than today.")
            return
        qty = self.qty.value()
        if qty <= 0:
            warn(self, "Quantity needed", "Enter a quantity greater than zero.")
            self.qty.focus_set()
            return
        party = self.party.get().strip()
        if not party:
            warn(self, "Name needed", "Enter the supplier name." if self.is_in
                 else "Enter who the materials were issued to.")
            self.party.focus_set()
            return
        extra = self._extra_values()
        if extra is None:
            return

        data = dict(material_id=m["id"], txn_date=txn_date, quantity=qty, party_name=party,
                    party_details=self.party_details.get(), reference_no=self.ref.get(),
                    remarks=self.remarks.get("1.0", "end").strip(), extra_fields=extra)
        try:
            if self.txn:
                self.db.update_transaction(self.txn["id"], **data)
                txn_id = self.txn["id"]
            else:
                txn_id = self.db.add_transaction(self.txn_type, **data)
        except ValidationError as exc:
            warn(self, "Entry not saved", str(exc))
            self.reload_lists()
            return

        if not self.txn:
            verb = "Received" if self.is_in else "Issued"
            self.saved_label.configure(
                foreground=theme.RECEIVE if self.is_in else theme.ISSUE,
                text=f"Saved entry no. {txn_id}: {verb} {fmt_qty(qty)} {m['unit']} of "
                     f"{m['name']}. Ready for the next entry.")
            self.reload_lists()
            self.clear(keep_date=True)
        if self.on_saved:
            self.on_saved(txn_id)

    def _create_material(self, name: str) -> bool:
        if not confirm(self, "New material",
                       f"'{name}' is not in your material list yet.\n\nAdd it as a new material?"):
            return False
        values = MaterialDialog(self, name=name, title="Add new material").show()
        if not values:
            return False
        try:
            self.db.add_material(**values)
        except ValidationError as exc:
            warn(self, "Material not added", str(exc))
            return False
        self.reload_lists()
        self.material.set(values["name"])
        self._on_material_changed()
        return True


class EditEntryDialog(Modal):
    def __init__(self, parent, db: Database, txn_id: int):
        txn = db.get_transaction(txn_id)
        kind = "incoming" if txn["txn_type"] == IN else "outgoing"
        super().__init__(parent, f"Edit {kind} entry no. {txn_id}")
        ttk.Label(self.body, text=f"Edit {kind} entry no. {txn_id}",
                  style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(self.body, text=f"Entered by {txn['created_by']} on "
                                  f"{txn['created_at'].replace('T', ' at ')}",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(0, 6))
        self.form = EntryForm(self.body, db, txn["txn_type"], txn=txn, on_saved=self._saved,
                              on_cancel=self.cancel)
        self.form.pack(fill="both", expand=True)
        self.minsize(600, 0)

    def _saved(self, _txn_id: int):
        self.result = True
        self.destroy()
