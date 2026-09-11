"""Stand-alone dialogs: first-run setup, material editor, about."""
from __future__ import annotations

import platform
import tkinter as tk
from tkinter import ttk

from ..database import Database
from ..paths import data_dir
from ..version import __app_name__, __description__, __dev_company__, __developer__, __version__
from .widgets import Modal, QtyField, warn

COMMON_UNITS = ["pcs", "kg", "g", "ton", "m", "m2", "m3", "L", "box", "bag", "roll",
                "set", "pack", "pair", "sheet", "drum", "bundle"]


def _form_row(parent, row: int, text: str, widget: tk.Widget) -> None:
    ttk.Label(parent, text=text, style="Card.TLabel").grid(row=row, column=0, sticky="w",
                                                            padx=(0, 14), pady=6)
    widget.grid(row=row, column=1, sticky="ew", pady=6)


class SetupDialog(Modal):
    """Company name and user name. Shown on first start and from Settings."""

    def __init__(self, parent, db: Database, first_run: bool = True):
        super().__init__(parent, f"Welcome to {__app_name__}" if first_run else "Company and user")
        self.db = db
        b = self.body
        b.columnconfigure(1, weight=1)
        row = 0
        if first_run:
            ttk.Label(b, text="Let's set up your warehouse", style="CardTitle.TLabel").grid(
                row=0, column=0, columnspan=2, sticky="w")
            ttk.Label(b, text="You can change these details later in Settings.",
                      style="CardMuted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w",
                                                     pady=(0, 10))
            row = 2
        self.company = ttk.Entry(b, width=40)
        self.company.insert(0, db.company_name)
        self.user = ttk.Entry(b, width=40)
        self.user.insert(0, db.get_setting("username"))
        _form_row(b, row, "Company name", self.company)
        _form_row(b, row + 1, "Your name", self.user)
        ttk.Label(b, text="Your name is saved with every entry you make.",
                  style="CardMuted.TLabel").grid(row=row + 2, column=1, sticky="w")
        buttons = ttk.Frame(b, style="Card.TFrame")
        buttons.grid(row=row + 3, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save and continue" if first_run else "Save",
                   style="Primary.TButton", command=self._save).pack(side="right")
        self.bind("<Return>", lambda _: self._save())
        self.company.focus_set()

    def _save(self):
        company, user = self.company.get().strip(), self.user.get().strip()
        if not company:
            warn(self, "Company name needed", "Enter your company name.")
            self.company.focus_set()
            return
        if not user:
            warn(self, "Your name needed", "Enter your name. It is saved with every entry you make.")
            self.user.focus_set()
            return
        self.db.set_setting("company_name", company)
        self.db.set_setting("username", user)
        self.result = True
        self.destroy()


class MaterialDialog(Modal):
    def __init__(self, parent, name: str = "", unit: str = "pcs", min_stock: float = 0,
                 title: str = "Material"):
        super().__init__(parent, title)
        b = self.body
        b.columnconfigure(1, weight=1)
        ttk.Label(b, text=title, style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2,
                                                                 sticky="w", pady=(0, 8))
        self.name = ttk.Entry(b, width=36)
        self.name.insert(0, name)
        self.unit = ttk.Combobox(b, values=COMMON_UNITS, width=34)
        self.unit.set(unit or "pcs")
        self.min_stock = QtyField(b)
        self.min_stock.set_value(min_stock)
        _form_row(b, 1, "Material name", self.name)
        _form_row(b, 2, "Unit of measure", self.unit)
        _form_row(b, 3, "Low-stock warning at", self.min_stock)
        ttk.Label(b, text="The stock balance screen highlights this material when its balance\n"
                          "reaches this number. Leave empty or 0 for no warning.",
                  style="CardMuted.TLabel", justify="left").grid(row=4, column=1, sticky="w")
        buttons = ttk.Frame(b, style="Card.TFrame")
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancel", command=self.cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save material", style="Primary.TButton",
                   command=self._save).pack(side="right")
        self.bind("<Return>", lambda _: self._save())
        (self.unit if name else self.name).focus_set()

    def _save(self):
        if not self.name.get().strip():
            warn(self, "Name needed", "Enter a material name.")
            return
        self.result = {"name": self.name.get().strip(),
                       "unit": self.unit.get().strip() or "pcs",
                       "min_stock": self.min_stock.value()}
        self.destroy()


class AboutDialog(Modal):
    def __init__(self, parent):
        super().__init__(parent, f"About {__app_name__}")
        b = self.body
        ttk.Label(b, text=__app_name__, style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(b, text=f"Version {__version__}", style="CardBold.TLabel").pack(anchor="w")
        ttk.Label(b, text=__description__, style="CardMuted.TLabel", wraplength=420).pack(
            anchor="w", pady=(2, 14))
        grid = ttk.Frame(b, style="Card.TFrame")
        grid.pack(anchor="w")
        rows = [
            ("Developer", __developer__),
            ("Company", __dev_company__),
            ("Data folder", str(data_dir())),
            ("Platform", f"Python {platform.python_version()}, Tk {tk.TkVersion}, "
                         f"{platform.system()} {platform.release()}"),
        ]
        for i, (key, value) in enumerate(rows):
            ttk.Label(grid, text=key, style="CardBold.TLabel").grid(row=i, column=0, sticky="nw",
                                                                    padx=(0, 14), pady=2)
            ttk.Label(grid, text=value, style="Card.TLabel", wraplength=340).grid(
                row=i, column=1, sticky="w", pady=2)
        ttk.Label(b, text=f"© {__dev_company__}. All rights reserved.",
                  style="CardMuted.TLabel").pack(anchor="w", pady=(16, 0))
        ttk.Button(b, text="Close", command=self.cancel).pack(anchor="e", pady=(12, 0))
