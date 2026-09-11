"""Main window: sidebar navigation, header, pages, menu and shortcuts."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..database import IN, OUT, Database
from ..version import __app_name__, __version__
from . import theme
from .dialogs import AboutDialog
from .pages import (
    BalancePage, EntryPage, HomePage, MaterialsPage, RecordsPage, SettingsPage, ask_save_path,
    run_export,
)
from .theme import FONTS
from .widgets import NavItem

NAV = [
    ("home", "Home", "Control-h", "Ctrl+H"),
    ("in", "Receive (incoming)", "Control-i", "Ctrl+I"),
    ("out", "Issue (outgoing)", "Control-o", "Ctrl+O"),
    ("balance", "Stock balance", "Control-b", "Ctrl+B"),
    ("records", "All records", "Control-r", "Ctrl+R"),
    ("materials", "Materials", "Control-m", "Ctrl+M"),
    ("settings", "Settings", None, None),
]


class MainWindow:
    def __init__(self, root: tk.Tk, db: Database):
        self.root = root
        self.db = db
        root.title(f"{__app_name__} {__version__}")
        root.minsize(1100, 680)

        self._build_menu()
        self._build_sidebar()

        content = ttk.Frame(root)
        content.pack(side="left", fill="both", expand=True)
        header = tk.Frame(content, background=theme.SURFACE, padx=28, pady=12,
                          highlightthickness=0)
        header.pack(fill="x")
        tk.Frame(content, background=theme.LINE, height=1).pack(fill="x")
        self.company_label = tk.Label(header, font=FONTS["company"], foreground=theme.STEEL,
                                      background=theme.SURFACE)
        self.company_label.pack(side="left")
        self.user_label = tk.Label(header, foreground=theme.MUTED, background=theme.SURFACE)
        self.user_label.pack(side="right")

        self.status = ttk.Label(content, text="", style="Status.TLabel", anchor="w")
        self.status.pack(side="bottom", fill="x")

        stack = ttk.Frame(content)
        stack.pack(fill="both", expand=True)
        stack.rowconfigure(0, weight=1)
        stack.columnconfigure(0, weight=1)
        self.pages = {
            "home": HomePage(stack, db, self.go),
            "in": EntryPage(stack, db, IN),
            "out": EntryPage(stack, db, OUT),
            "balance": BalancePage(stack, db),
            "records": RecordsPage(stack, db),
            "materials": MaterialsPage(stack, db),
            "settings": SettingsPage(stack, db, self.update_header),
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        for key, _text, sequence, _label in NAV:
            if sequence:
                root.bind_all(f"<{sequence}>", lambda _e, k=key: self.go(k))
        root.bind_all("<Control-e>", lambda _e: self.export_everything())
        root.bind_all("<Control-q>", lambda _e: root.destroy())

        self.update_header()
        self.go("home")

    # -------------------------------------------------------------- build ---
    def _build_sidebar(self):
        side = tk.Frame(self.root, background=theme.STEEL, width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text=__app_name__, font=FONTS["app_title"], foreground="white",
                 background=theme.STEEL, anchor="w", padx=20, pady=18).pack(fill="x")
        self.nav: dict[str, NavItem] = {}
        for key, text, _seq, _label in NAV:
            item = NavItem(side, text, lambda k=key: self.go(k))
            item.pack(fill="x")
            self.nav[key] = item
        tk.Label(side, text=f"Version {__version__}", foreground="#9FB0C2",
                 background=theme.STEEL, anchor="w", padx=20, pady=12).pack(side="bottom", fill="x")
        NavItem(side, "About", self.show_about).pack(side="bottom", fill="x")
        NavItem(side, "Export to Excel", self.export_everything).pack(side="bottom", fill="x")

    def _build_menu(self):
        bar = tk.Menu(self.root)
        file_menu = tk.Menu(bar, tearoff=False)
        file_menu.add_command(label="Export everything to Excel...", accelerator="Ctrl+E",
                              command=self.export_everything)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Ctrl+Q", command=self.root.destroy)
        bar.add_cascade(label="File", menu=file_menu)
        go_menu = tk.Menu(bar, tearoff=False)
        for key, text, _seq, label in NAV:
            go_menu.add_command(label=text, accelerator=label or "", command=lambda k=key: self.go(k))
        bar.add_cascade(label="Go to", menu=go_menu)
        help_menu = tk.Menu(bar, tearoff=False)
        help_menu.add_command(label=f"About {__app_name__}", command=self.show_about)
        bar.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=bar)

    # ------------------------------------------------------------ actions ---
    def go(self, key: str):
        if key == "export":
            self.export_everything()
            return
        low_only = key == "balance_low"
        if low_only:
            key = "balance"
        for nav_key, item in self.nav.items():
            item.set_active(nav_key == key)
        page = self.pages[key]
        page.tkraise()
        if low_only:
            page.show_low_only()
        if hasattr(page, "on_show"):
            page.on_show()
        else:
            page.refresh()

    def update_header(self):
        self.company_label.configure(text=self.db.company_name or __app_name__)
        self.user_label.configure(text=f"User: {self.db.username}")
        self.status.configure(text=f"Signed in as {self.db.username}")

    def export_everything(self):
        path = ask_save_path(self.root, self.db, "Warehouse_Export")
        if path:
            run_export(self.root, "export_all", self.db, path)

    def show_about(self):
        AboutDialog(self.root).show()
