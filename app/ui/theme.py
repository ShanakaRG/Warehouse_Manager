"""Visual system for the Tkinter UI.

Steel    #243447  structure: sidebar, headings
Concrete #EDEFF2  window background
Receive  #2E7D4F  everything about incoming stock
Issue    #B8660B  everything about outgoing stock
Safety   #F2B705  used sparingly: current page marker, low-stock rows
Danger   #B42318  delete, out of stock
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

STEEL = "#243447"
STEEL_HOVER = "#2F4459"
STEEL_ACTIVE = "#33495F"
CONCRETE = "#EDEFF2"
SURFACE = "#FFFFFF"
SURFACE_HOVER = "#F6F8FA"
LINE = "#D5DAE1"
TEXT = "#1E2A36"
MUTED = "#5B6775"
NAV_TEXT = "#D7E0EA"
RECEIVE = "#2E7D4F"
RECEIVE_DARK = "#256B42"
ISSUE = "#B8660B"
ISSUE_DARK = "#9C5609"
SAFETY = "#F2B705"
DANGER = "#B42318"
LOW_TINT = "#FFF1C2"
OUT_TINT = "#FBE3E0"
STRIPE = "#F7F8FA"
SELECT = "#CFE0F3"
LINK = "#2F5F93"

FONTS: dict[str, tuple] = {}


def _pick_family(root: tk.Misc) -> str:
    available = set(tkfont.families(root))
    for family in ("Segoe UI", "Calibri", "Helvetica Neue", "DejaVu Sans", "Arial"):
        if family in available:
            return family
    return tkfont.nametofont("TkDefaultFont").actual("family")


def setup(root: tk.Tk) -> None:
    family = _pick_family(root)
    FONTS.update(
        base=(family, 10), small=(family, 9), bold=(family, 10, "bold"),
        h1=(family, 16, "bold"), h2=(family, 12, "bold"), company=(family, 16, "bold"),
        tile_title=(family, 14, "bold"), tile_hint=(family, 10),
        nav=(family, 11), nav_active=(family, 11, "bold"), big=(family, 12, "bold"),
        app_title=(family, 12, "bold"),
    )
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkFixedFont"):
        try:
            tkfont.nametofont(name).configure(family=family, size=10)
        except tk.TclError:
            pass
    root.configure(background=CONCRETE)
    root.option_add("*TCombobox*Listbox.font", FONTS["base"])
    root.option_add("*TCombobox*Listbox.selectBackground", SELECT)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=CONCRETE, foreground=TEXT, font=FONTS["base"],
                bordercolor=LINE, focuscolor=SELECT)

    # frames & labels
    s.configure("TFrame", background=CONCRETE)
    s.configure("Card.TFrame", background=SURFACE)
    s.configure("TLabel", background=CONCRETE, foreground=TEXT)
    s.configure("Card.TLabel", background=SURFACE)
    s.configure("Title.TLabel", font=FONTS["h1"], foreground=STEEL)
    s.configure("Muted.TLabel", foreground=MUTED)
    s.configure("CardTitle.TLabel", background=SURFACE, font=FONTS["h2"], foreground=STEEL)
    s.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED)
    s.configure("CardBold.TLabel", background=SURFACE, font=FONTS["bold"])
    s.configure("Available.TLabel", background=SURFACE, font=FONTS["big"], foreground=ISSUE)
    s.configure("Warning.TLabel", background=SURFACE, font=FONTS["bold"], foreground=DANGER)
    s.configure("Saved.TLabel", background=SURFACE, font=FONTS["bold"], foreground=RECEIVE)

    # inputs
    field = dict(fieldbackground=SURFACE, bordercolor="#B9C2CC", lightcolor=SURFACE,
                 darkcolor=SURFACE, padding=6, insertcolor=TEXT)
    s.configure("TEntry", **field)
    s.map("TEntry", bordercolor=[("focus", "#3A6EA5")], lightcolor=[("focus", "#3A6EA5")],
          fieldbackground=[("disabled", "#F3F4F6")])
    s.configure("TCombobox", **field, arrowsize=15, arrowcolor=STEEL, background=SURFACE)
    s.map("TCombobox", bordercolor=[("focus", "#3A6EA5")], lightcolor=[("focus", "#3A6EA5")],
          fieldbackground=[("readonly", SURFACE), ("disabled", "#F3F4F6")],
          selectbackground=[("readonly", SURFACE)], selectforeground=[("readonly", TEXT)])
    s.configure("TCheckbutton", background=CONCRETE)
    s.map("TCheckbutton", background=[("active", CONCRETE)])

    # buttons
    s.configure("TButton", padding=(14, 7), background="#E3E7EC", bordercolor="#C9D0D8",
                lightcolor="#E3E7EC", darkcolor="#E3E7EC", relief="flat")
    s.map("TButton", background=[("disabled", "#EEF0F3"), ("active", "#D6DCE3")],
          foreground=[("disabled", "#9AA3AD")])
    for name, bg, hover in (("Primary", STEEL, STEEL_ACTIVE), ("Receive", RECEIVE, RECEIVE_DARK),
                            ("Issue", ISSUE, ISSUE_DARK)):
        s.configure(f"{name}.TButton", background=bg, foreground="white", font=FONTS["bold"],
                    bordercolor=bg, lightcolor=bg, darkcolor=bg, padding=(18, 9))
        s.map(f"{name}.TButton", background=[("disabled", "#AAB2BC"), ("active", hover)],
              foreground=[("disabled", "#EEF0F3")], lightcolor=[("active", hover)],
              darkcolor=[("active", hover)])
    s.configure("Danger.TButton", background=SURFACE, foreground=DANGER, bordercolor=DANGER,
                lightcolor=SURFACE, darkcolor=SURFACE)
    s.map("Danger.TButton", background=[("active", "#FCEBEA")])
    for name, bg in (("Link", CONCRETE), ("CardLink", SURFACE)):
        s.configure(f"{name}.TButton", background=bg, foreground=LINK, bordercolor=bg,
                    lightcolor=bg, darkcolor=bg, padding=(2, 4), relief="flat")
        s.map(f"{name}.TButton", background=[("active", bg)], foreground=[("active", STEEL)])

    # tables
    s.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT,
                rowheight=30, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
    s.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", TEXT)])
    s.configure("Treeview.Heading", background="#F1F3F6", foreground=STEEL, font=FONTS["bold"],
                padding=(8, 7), bordercolor=LINE, lightcolor="#F1F3F6", darkcolor=LINE,
                relief="flat")
    s.map("Treeview.Heading", background=[("active", "#E4E8ED")])
    s.configure("Vertical.TScrollbar", background="#D6DCE3", troughcolor=CONCRETE,
                bordercolor=CONCRETE, arrowcolor=STEEL, lightcolor="#D6DCE3", darkcolor="#D6DCE3")
    s.configure("Horizontal.TScrollbar", background="#D6DCE3", troughcolor=CONCRETE,
                bordercolor=CONCRETE, arrowcolor=STEEL, lightcolor="#D6DCE3", darkcolor="#D6DCE3")
    s.configure("Status.TLabel", background=SURFACE, foreground=MUTED, padding=(10, 4))
