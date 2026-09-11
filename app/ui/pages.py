"""The screens shown in the main window."""
from __future__ import annotations

import os
import subprocess
import sys
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from ..database import IN, OUT, Database, ValidationError
from ..paths import backup_dir, data_dir, db_path
from ..utils import STATUS_LOW, STATUS_OUT, fmt_qty, iso_to_display
from . import theme
from .dialogs import MaterialDialog, SetupDialog
from .entry_form import EditEntryDialog, EntryForm
from .theme import FONTS
from .widgets import (
    DataTable, DateField, ScrollFrame, Tile, card, confirm, info, page_header, warn,
)


# ------------------------------------------------------------------ helpers ---
def open_path(path) -> None:
    """Open a file or folder with the default Windows program."""
    path = str(path)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa: S606 - opening the user's own file
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


def edit_entry(parent, db: Database, txn_id: int | None) -> bool:
    if txn_id is None:
        warn(parent, "No entry selected", "Click an entry in the list first, then press Edit.")
        return False
    if db.get_transaction(txn_id) is None:
        warn(parent, "Entry not found", "This entry no longer exists.")
        return False
    return bool(EditEntryDialog(parent, db, txn_id).show())


def delete_entry(parent, db: Database, txn_id: int | None) -> bool:
    if txn_id is None:
        warn(parent, "No entry selected", "Click an entry in the list first, then press Delete.")
        return False
    t = db.get_transaction(txn_id)
    if not t:
        return False
    kind = "incoming" if t["txn_type"] == IN else "outgoing"
    if not confirm(parent, "Delete entry?",
                   f"Delete {kind} entry no. {t['id']}?\n\n"
                   f"{fmt_qty(t['quantity'])} {t['unit']} of {t['material_name']} "
                   f"({t['party_name']})\n\nThis cannot be undone. "
                   "The deletion is recorded in the change history."):
        return False
    try:
        db.delete_transaction(txn_id)
    except ValidationError as exc:
        warn(parent, "Entry not deleted", str(exc))
        return False
    return True


def ask_save_path(parent, db: Database, suggested: str) -> str | None:
    company = "".join(c if c.isalnum() else "_" for c in (db.company_name or "Warehouse")).strip("_")
    documents = Path.home() / "Documents"
    path = filedialog.asksaveasfilename(
        parent=parent, title="Save Excel file", defaultextension=".xlsx",
        initialdir=str(documents if documents.exists() else Path.home()),
        initialfile=f"{company}_{suggested}_{date.today():%Y-%m-%d}.xlsx",
        filetypes=[("Excel files", "*.xlsx")])
    return path or None


def run_export(parent, func_name: str, *args) -> None:
    """func_name: 'export_all' | 'export_balance' | 'export_transactions'.
    Imported here so the program still starts if the Excel library is missing."""
    try:
        from .. import export
    except ImportError:
        warn(parent, "Excel library missing",
             "Excel export needs the 'openpyxl' library.\n\n"
             "Close the program, run runner.bat and choose 'Install / update libraries'.")
        return
    try:
        path = getattr(export, func_name)(*args)
    except PermissionError:
        warn(parent, "File is in use",
             "The file could not be saved. If it is open in Excel, close it and try again.")
        return
    if confirm(parent, "Export finished", f"Saved to:\n{path}\n\nOpen the file now?"):
        open_path(path)


TXN_COLUMNS = [("No.", 60, "e"), ("Type", 90, "w"), ("Date", 95, "w"), ("Material", 170, "w"),
               ("Quantity", 110, "e"), ("Supplier / Issued to", 170, "w"), ("Details", 150, "w"),
               ("Reference no.", 110, "w"), ("Remarks", 160, "w"),
               ("Additional details", 180, "w"), ("Entered by", 110, "w")]


def make_txn_table(parent, txn_type: str | None = None, height: int = 8) -> DataTable:
    table = DataTable(parent, TXN_COLUMNS, sort_column=2, descending=True, height=height)
    if txn_type is not None:
        table.tree["displaycolumns"] = [c for c in table._ids if c != "c1"]
        table.headings[5] = "Supplier" if txn_type == IN else "Issued to"
    return table


def load_txn_table(table: DataTable, txns: list[dict]) -> None:
    rows = []
    for t in txns:
        is_in = t["txn_type"] == IN
        sign = "+" if is_in else "−"
        extras = "; ".join(f"{k}: {v}" for k, v in t["extra_fields"].items())
        values = [t["id"], "Incoming" if is_in else "Outgoing", iso_to_display(t["txn_date"]),
                  t["material_name"], f"{sign}{fmt_qty(t['quantity'])} {t['unit']}",
                  t["party_name"], t["party_details"], t["reference_no"],
                  t["remarks"].replace("\n", " "), extras, t["created_by"]]
        keys = [t["id"], values[1], f"{t['txn_date']}-{t['id']:010d}", t["material_name"],
                t["quantity"] if is_in else -t["quantity"], t["party_name"], t["party_details"],
                t["reference_no"], values[8], extras, t["created_by"]]
        rows.append((str(t["id"]), values, keys, ()))
    table.load(rows)


def button_row(parent, *specs) -> ttk.Frame:
    """specs: (text, command, style) ... returns a frame with buttons packed left."""
    frame = ttk.Frame(parent)
    for text, command, style in specs:
        ttk.Button(frame, text=text, command=command, style=style or "TButton").pack(
            side="left", padx=(0, 8))
    return frame


class Page(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=(28, 20, 28, 16))

    def refresh(self):
        pass


# --------------------------------------------------------------------- home ---
class HomePage(Page):
    def __init__(self, parent, db: Database, navigate: Callable[[str], None]):
        super().__init__(parent)
        self.db = db
        self.navigate = navigate
        self.welcome = ttk.Label(self, text="", style="Title.TLabel")
        self.welcome.pack(anchor="w")
        ttk.Label(self, text="What would you like to do?", style="Muted.TLabel").pack(anchor="w")

        grid = ttk.Frame(self)
        grid.pack(fill="x", pady=(16, 16))
        grid.columnconfigure((0, 1), weight=1, uniform="tiles")
        tiles = [
            ("in", "Receive materials", "Record stock coming into the warehouse", theme.RECEIVE),
            ("out", "Issue materials", "Record stock going out of the warehouse", theme.ISSUE),
            ("balance", "Check stock balance", "See how much of each material you have", theme.STEEL),
            ("export", "Export to Excel", "Save every record to an Excel file", theme.STEEL),
        ]
        for i, (key, title, hint, accent) in enumerate(tiles):
            Tile(grid, title, hint, accent, lambda k=key: navigate(k)).grid(
                row=i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 8, 0 if i % 2 else 8),
                pady=8)

        outer, inner = card(self)
        outer.pack(fill="x")
        ttk.Label(inner, text="Today at a glance", style="CardTitle.TLabel").pack(anchor="w")
        self.line1 = tk.Frame(inner, background=theme.SURFACE)
        self.line1.pack(anchor="w", pady=(6, 0))
        self.line2 = ttk.Label(inner, text="", style="Card.TLabel")
        self.line2.pack(anchor="w")
        self.line3 = ttk.Label(inner, text="", style="Card.TLabel")
        self.line3.pack(anchor="w")
        self.low_link = ttk.Button(inner, text="View low-stock materials", style="CardLink.TButton",
                                   command=lambda: navigate("balance_low"))
        self.low_link.pack(anchor="w", pady=(6, 0))

    def refresh(self):
        self.welcome.configure(text=f"Hello, {self.db.username}")
        s = self.db.dashboard_stats()
        for child in self.line1.winfo_children():
            child.destroy()
        parts = [(str(s["today_in"]), theme.RECEIVE, True), (" incoming and ", theme.RECEIVE, False),
                 (str(s["today_out"]), theme.ISSUE, True), (" outgoing", theme.ISSUE, False),
                 (" entries today.", theme.TEXT, False)]
        for text, color, bold in parts:
            tk.Label(self.line1, text=text, foreground=color, background=theme.SURFACE, padx=0,
                     font=FONTS["bold"] if bold else FONTS["base"]).pack(side="left")
        self.line2.configure(text=f"{s['materials']} materials in your list.")
        if s["low"] or s["out"]:
            self.line3.configure(text=f"{s['low']} low on stock, {s['out']} out of stock.",
                                 foreground=theme.DANGER)
            self.low_link.pack(anchor="w", pady=(6, 0))
        else:
            self.line3.configure(text="No materials are running low.", foreground=theme.TEXT)
            self.low_link.pack_forget()


# ------------------------------------------------------------ entry pages ---
class EntryPage(Page):
    """Form on the left, this type's recent entries on the right."""

    def __init__(self, parent, db: Database, txn_type: str):
        super().__init__(parent)
        self.db = db
        self.txn_type = txn_type
        is_in = txn_type == IN
        page_header(
            self, "Receive materials (incoming)" if is_in else "Issue materials (outgoing)",
            "Fill in the details and press Save. Fields marked * are required." if is_in else
            "You can only issue what is in stock. The quantity box will not accept more "
            "than the available balance.").pack(fill="x", pady=(0, 10))

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2, minsize=560)   # form always gets room
        body.columnconfigure(1, weight=3, minsize=380)
        body.rowconfigure(0, weight=1)

        left = ScrollFrame(body)
        outer, inner = card(left.body, accent=theme.RECEIVE if is_in else theme.ISSUE)
        outer.pack(fill="x", padx=(0, 10))
        self.form = EntryForm(inner, db, txn_type, on_saved=lambda _id: self.refresh_table())
        self.form.pack(fill="both", expand=True)
        left.grid(row=0, column=0, sticky="nsew")

        right = ttk.Frame(body, padding=(10, 0, 0, 0))
        ttk.Label(right, text="Recent incoming entries" if is_in else "Recent outgoing entries",
                  font=FONTS["h2"], foreground=theme.STEEL).pack(anchor="w", pady=(0, 6))
        self.table = make_txn_table(right, txn_type)
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self._edit)
        bar = button_row(right, ("Edit selected", self._edit, None),
                         ("Delete selected", self._delete, "Danger.TButton"))
        bar.pack(fill="x", pady=(8, 0))
        ttk.Label(bar, text="Latest 100 shown.",
                  style="Muted.TLabel").pack(side="right")
        right.grid(row=0, column=1, sticky="nsew")

    def refresh(self):
        self.form.reload_lists()
        self.refresh_table()

    def refresh_table(self):
        load_txn_table(self.table, self.db.list_transactions(txn_type=self.txn_type, limit=100))

    def _edit(self):
        if edit_entry(self, self.db, self.table.selected_id()):
            self.refresh()

    def _delete(self):
        if delete_entry(self, self.db, self.table.selected_id()):
            self.refresh()


# ------------------------------------------------------------ stock balance ---
class BalancePage(Page):
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        page_header(self, "Stock balance",
                    "Balance = total received − total issued. It can never be below zero.").pack(
            fill="x", pady=(0, 10))
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Search").pack(side="left", padx=(0, 6))
        self.search = tk.StringVar()
        self.search.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(bar, textvariable=self.search, width=32).pack(side="left")
        self.only_low = tk.BooleanVar()
        ttk.Checkbutton(bar, text="Show only low or out-of-stock", variable=self.only_low,
                        command=self.refresh).pack(side="left", padx=16)
        ttk.Button(bar, text="Export balance to Excel", style="Primary.TButton",
                   command=self._export).pack(side="right")
        self.table = DataTable(self, [("Material", 220, "w"), ("Unit", 70, "w"),
                                      ("Total received", 120, "e"), ("Total issued", 120, "e"),
                                      ("Balance", 110, "e"), ("Low-stock level", 120, "e"),
                                      ("Status", 130, "w")], height=8)
        self.table.pack(fill="both", expand=True)
        self.footer = ttk.Label(self, text="", style="Muted.TLabel")
        self.footer.pack(anchor="w", pady=(6, 0))

    def show_low_only(self):
        self.only_low.set(True)

    def refresh(self):
        rows = self.db.stock_balance()
        text = self.search.get().strip().lower()
        if text:
            rows = [r for r in rows if text in r["name"].lower()]
        if self.only_low.get():
            rows = [r for r in rows if r["status"] in (STATUS_LOW, STATUS_OUT)]
        tags = {STATUS_LOW: ("low",), STATUS_OUT: ("out",)}
        self.table.load([
            (str(m["id"]),
             [m["name"], m["unit"], fmt_qty(m["total_in"]), fmt_qty(m["total_out"]),
              fmt_qty(m["balance"]), fmt_qty(m["min_stock"]) if m["min_stock"] else "-", m["status"]],
             [m["name"], m["unit"], m["total_in"], m["total_out"], m["balance"], m["min_stock"],
              m["status"]],
             tags.get(m["status"], ()))
            for m in rows])
        self.footer.configure(text=f"{len(rows)} materials shown. "
                                   f"Updated {datetime.now():%d/%m/%Y %H:%M}.")

    def _export(self):
        path = ask_save_path(self, self.db, "Stock_Balance")
        if path:
            run_export(self, "export_balance", self.db, path)


# ----------------------------------------------------------------- records ---
class RecordsPage(Page):
    TYPES = {"Incoming and outgoing": None, "Incoming only": IN, "Outgoing only": OUT}

    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self._rows: list[dict] = []
        self._material_ids: dict[str, int | None] = {}
        page_header(self, "All records",
                    "Find, edit or delete any entry. Double-click a row to edit it.").pack(
            fill="x", pady=(0, 10))
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 8))
        self.type = ttk.Combobox(bar, values=list(self.TYPES), state="readonly", width=22)
        self.type.set("Incoming and outgoing")
        self.material = ttk.Combobox(bar, state="readonly", width=24)
        self.use_dates = tk.BooleanVar()
        self.date_from = DateField(bar, style_bg=theme.CONCRETE)
        self.date_to = DateField(bar, style_bg=theme.CONCRETE)
        self.date_from.set_date(date.today() - timedelta(days=30))
        self.search = ttk.Entry(bar, width=26)
        self.type.pack(side="left")
        self.material.pack(side="left", padx=8)
        ttk.Checkbutton(bar, text="Between", variable=self.use_dates,
                        command=self._toggle_dates).pack(side="left", padx=(8, 4))
        self.date_from.pack(side="left")
        ttk.Label(bar, text="and").pack(side="left", padx=6)
        self.date_to.pack(side="left")
        self.search.pack(side="left", padx=(12, 6), fill="x", expand=True)
        ttk.Button(bar, text="Search", command=self.refresh).pack(side="left")
        for w in (self.type, self.material):
            w.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.search.bind("<Return>", lambda _: self.refresh())
        self._toggle_dates(refresh=False)

        self.table = make_txn_table(self, height=8)
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self._edit)
        bottom = button_row(self, ("Edit selected", self._edit, None),
                            ("Delete selected", self._delete, "Danger.TButton"))
        bottom.pack(fill="x", pady=(8, 0))
        self.count = ttk.Label(bottom, text="", style="Muted.TLabel")
        self.count.pack(side="left", padx=8)
        ttk.Button(bottom, text="Export these records to Excel", style="Primary.TButton",
                   command=self._export).pack(side="right")

    def _toggle_dates(self, refresh: bool = True):
        state = "normal" if self.use_dates.get() else "disabled"
        self.date_from.configure_state(state)
        self.date_to.configure_state(state)
        if refresh:
            self.refresh()

    def _reload_materials(self):
        current = self.material.get()
        self._material_ids = {"All materials": None}
        self._material_ids.update({m["name"]: m["id"] for m in self.db.stock_balance()})
        self.material.configure(values=list(self._material_ids))
        self.material.set(current if current in self._material_ids else "All materials")

    def refresh(self):
        if not self._material_ids:
            self._reload_materials()
        dates = {}
        if self.use_dates.get():
            d_from, d_to = self.date_from.get_date(), self.date_to.get_date()
            if not d_from or not d_to:
                warn(self, "Date not recognised", "Enter dates as day/month/year, e.g. 25/08/2026.")
                return
            dates = {"date_from": d_from, "date_to": d_to}
        self._rows = self.db.list_transactions(
            txn_type=self.TYPES[self.type.get()], material_id=self._material_ids.get(self.material.get()),
            search=self.search.get(), **dates)
        load_txn_table(self.table, self._rows)
        self.count.configure(text=f"{len(self._rows)} entries")

    def on_show(self):
        self._reload_materials()
        self.refresh()

    def _edit(self):
        if edit_entry(self, self.db, self.table.selected_id()):
            self.refresh()

    def _delete(self):
        if delete_entry(self, self.db, self.table.selected_id()):
            self.refresh()

    def _export(self):
        if not self._rows:
            warn(self, "Nothing to export", "No entries match your filters.")
            return
        path = ask_save_path(self, self.db, "Records")
        if path:
            run_export(self, "export_transactions", self.db, path, self._rows,
                       f"Records ({self.type.get()}, {self.material.get()})")


# --------------------------------------------------------------- materials ---
class MaterialsPage(Page):
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        page_header(self, "Materials",
                    "Your list of materials, their units and low-stock warning levels. New "
                    "materials can also be added directly from the Receive screen.").pack(
            fill="x", pady=(0, 10))
        button_row(self, ("+ Add material", self._add, "Primary.TButton"),
                   ("Edit selected", self._edit, None),
                   ("Delete selected", self._delete, "Danger.TButton")).pack(fill="x", pady=(0, 8))
        self.table = DataTable(self, [("Material", 260, "w"), ("Unit", 80, "w"),
                                      ("Low-stock level", 130, "e"), ("Balance", 120, "e"),
                                      ("Entries", 90, "e")], height=8)
        self.table.pack(fill="both", expand=True)
        self.table.on_double_click(self._edit)

    def refresh(self):
        self.table.load([
            (str(m["id"]),
             [m["name"], m["unit"], fmt_qty(m["min_stock"]), fmt_qty(m["balance"]), m["entry_count"]],
             [m["name"], m["unit"], m["min_stock"], m["balance"], m["entry_count"]], ())
            for m in self.db.stock_balance()])

    def _add(self):
        values = MaterialDialog(self, title="Add material").show()
        if values:
            try:
                self.db.add_material(**values)
            except ValidationError as exc:
                warn(self, "Material not added", str(exc))
            self.refresh()

    def _selected(self):
        mid = self.table.selected_id()
        m = self.db.get_material(mid) if mid else None
        if not m:
            warn(self, "No material selected", "Click a material in the list first.")
        return m

    def _edit(self):
        m = self._selected()
        if not m:
            return
        values = MaterialDialog(self, m["name"], m["unit"], m["min_stock"], "Edit material").show()
        if values:
            try:
                self.db.update_material(m["id"], **values)
            except ValidationError as exc:
                warn(self, "Material not saved", str(exc))
            self.refresh()

    def _delete(self):
        m = self._selected()
        if m and confirm(self, "Delete material?", f"Delete '{m['name']}' from the material list?"):
            try:
                self.db.delete_material(m["id"])
            except ValidationError as exc:
                warn(self, "Material not deleted", str(exc))
            self.refresh()


# ---------------------------------------------------------------- settings ---
class SettingsPage(Page):
    def __init__(self, parent, db: Database, on_change: Callable[[], None]):
        super().__init__(parent)
        self.db = db
        self.on_change = on_change
        page_header(self, "Settings", "Company details, backups and data location.").pack(
            fill="x", pady=(0, 12))

        outer, inner = card(self)
        outer.pack(fill="x", pady=(0, 14))
        ttk.Label(inner, text="Company and user", style="CardTitle.TLabel").pack(anchor="w")
        self.details = ttk.Label(inner, text="", style="Card.TLabel", justify="left")
        self.details.pack(anchor="w", pady=6)
        ttk.Button(inner, text="Change company or user name", command=self._change).pack(anchor="w")

        outer, inner = card(self)
        outer.pack(fill="x")
        ttk.Label(inner, text="Backup", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(inner, style="CardMuted.TLabel", wraplength=700, justify="left",
                  text="A backup is a copy of all your data. Keep one on a USB drive or in the "
                       "cloud, so nothing is lost if this computer fails. A backup is also made "
                       "automatically each day the program is opened.").pack(anchor="w", pady=6)
        row = ttk.Frame(inner, style="Card.TFrame")
        row.pack(anchor="w")
        ttk.Button(row, text="Save a backup copy", style="Primary.TButton",
                   command=self._backup).pack(side="left")
        ttk.Button(row, text="Open data folder", command=lambda: open_path(data_dir())).pack(
            side="left", padx=8)
        ttk.Label(inner, text=f"Database file: {db_path()}", style="CardMuted.TLabel").pack(
            anchor="w", pady=(10, 0))

    def refresh(self):
        self.details.configure(text=f"Company:  {self.db.company_name}\nUser:  {self.db.username}")

    def _change(self):
        if SetupDialog(self, self.db, first_run=False).show():
            self.refresh()
            self.on_change()

    def _backup(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="Save backup", defaultextension=".db",
            initialdir=str(backup_dir()),
            initialfile=f"warehouse_backup_{datetime.now():%Y-%m-%d_%H%M}.db",
            filetypes=[("Backup files", "*.db")])
        if path:
            self.db.backup_to(path)
            info(self, "Backup saved", f"Backup saved to:\n{path}")
