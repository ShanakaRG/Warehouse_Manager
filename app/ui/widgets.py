"""Reusable Tkinter widgets. Pure standard library (no tkcalendar etc. needed)."""
from __future__ import annotations

import calendar
import re
import sys
import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, ttk
from typing import Callable

from . import theme
from .theme import FONTS


# ------------------------------------------------------------------ helpers ---
def warn(parent, title: str, text: str) -> None:
    messagebox.showwarning(title, text, parent=parent)


def info(parent, title: str, text: str) -> None:
    messagebox.showinfo(title, text, parent=parent)


def confirm(parent, title: str, text: str) -> bool:
    return messagebox.askyesno(title, text, parent=parent, default=messagebox.NO, icon="question")


def card(parent, accent: str | None = None, padding: int = 18) -> tuple[tk.Frame, ttk.Frame]:
    """White panel with a 1px border and an optional coloured top strip.
    Returns (outer, inner): place `outer`, put content into `inner`."""
    outer = tk.Frame(parent, background=theme.LINE, padx=1, pady=1)
    if accent:
        tk.Frame(outer, background=accent, height=4).pack(fill="x")
    inner = ttk.Frame(outer, style="Card.TFrame", padding=padding)
    inner.pack(fill="both", expand=True)
    return outer, inner


def page_header(parent, title: str, hint: str) -> ttk.Frame:
    box = ttk.Frame(parent)
    ttk.Label(box, text=title, style="Title.TLabel").pack(anchor="w")
    ttk.Label(box, text=hint, style="Muted.TLabel", wraplength=900, justify="left").pack(anchor="w")
    return box


def bind_mousewheel(widget: tk.Misc, target) -> None:
    """Scroll `target` (anything with yview_scroll) while the pointer is over `widget`."""
    def on_wheel(event):
        if event.num == 4:
            target.yview_scroll(-3, "units")
        elif event.num == 5:
            target.yview_scroll(3, "units")
        else:
            delta = event.delta if sys.platform == "darwin" else event.delta // 120
            target.yview_scroll(-delta * 3, "units")

    def enter(_):
        widget.bind_all("<MouseWheel>", on_wheel)
        widget.bind_all("<Button-4>", on_wheel)
        widget.bind_all("<Button-5>", on_wheel)

    def leave(_):
        widget.unbind_all("<MouseWheel>")
        widget.unbind_all("<Button-4>")
        widget.unbind_all("<Button-5>")

    widget.bind("<Enter>", enter, add="+")
    widget.bind("<Leave>", leave, add="+")


# -------------------------------------------------------------- scroll frame ---
class ScrollFrame(ttk.Frame):
    """A vertically scrollable area. Put children into `.body`."""

    def __init__(self, parent, background: str = theme.CONCRETE, **kw):
        super().__init__(parent, **kw)
        self.canvas = tk.Canvas(self, background=background, highlightthickness=0, borderwidth=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.body = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.body.bind("<Configure>", self._update_region)
        self.canvas.bind("<Configure>", self._fit_width)
        bind_mousewheel(self, self.canvas)

    def _update_region(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        needs_bar = self.body.winfo_reqheight() > self.canvas.winfo_height()
        if needs_bar:
            self.vbar.grid()
        else:
            self.vbar.grid_remove()
            self.canvas.yview_moveto(0)

    def _fit_width(self, event):
        self.canvas.itemconfigure(self._win, width=event.width)
        self._update_region()


# ---------------------------------------------------------------- date field ---
DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%y")


def parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class DateField(ttk.Frame):
    """Date entry (dd/mm/yyyy) with a pop-up calendar. Optionally no future dates."""

    def __init__(self, parent, allow_future: bool = False, style_bg: str = theme.SURFACE, **kw):
        super().__init__(parent, style="Card.TFrame" if style_bg == theme.SURFACE else "TFrame", **kw)
        self.allow_future = allow_future
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=12)
        self.entry.pack(side="left", fill="x", expand=True)
        self.button = ttk.Button(self, text="Calendar", command=self.open_calendar, takefocus=False)
        self.button.pack(side="left", padx=(6, 0))
        self.set_date(date.today())

    def set_date(self, value: date) -> None:
        self.var.set(value.strftime("%d/%m/%Y"))

    def get_date(self) -> date | None:
        return parse_date(self.var.get())

    def configure_state(self, state: str) -> None:
        self.entry.configure(state=state)
        self.button.configure(state=state)

    def open_calendar(self) -> None:
        CalendarPopup(self, self.get_date() or date.today(), self.allow_future, self.set_date)


class CalendarPopup(tk.Toplevel):
    def __init__(self, anchor: tk.Widget, current: date, allow_future: bool,
                 on_pick: Callable[[date], None]):
        super().__init__(anchor)
        self.withdraw()
        self.title("Pick a date")
        self.resizable(False, False)
        self.configure(background=theme.SURFACE, padx=10, pady=10)
        self.transient(anchor.winfo_toplevel())
        self.on_pick = on_pick
        self.allow_future = allow_future
        self.selected = current
        self.year, self.month = current.year, current.month

        nav = tk.Frame(self, background=theme.SURFACE)
        nav.pack(fill="x", pady=(0, 6))
        ttk.Button(nav, text="<", width=3, command=lambda: self._shift(-1)).pack(side="left")
        self.title_label = tk.Label(nav, background=theme.SURFACE, foreground=theme.STEEL,
                                    font=FONTS["h2"])
        self.title_label.pack(side="left", expand=True)
        self.next_btn = ttk.Button(nav, text=">", width=3, command=lambda: self._shift(1))
        self.next_btn.pack(side="right")
        self.grid_frame = tk.Frame(self, background=theme.SURFACE)
        self.grid_frame.pack()
        ttk.Button(self, text="Today", command=lambda: self._pick(date.today())).pack(pady=(8, 0))
        self.bind("<Escape>", lambda _: self.destroy())
        self._draw()

        self.update_idletasks()
        x = anchor.winfo_rootx()
        y = anchor.winfo_rooty() + anchor.winfo_height() + 2
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.grab_set()
        self.focus_set()

    def _shift(self, months: int):
        month = self.month + months
        self.year += (month - 1) // 12
        self.month = (month - 1) % 12 + 1
        self._draw()

    def _draw(self):
        for child in self.grid_frame.winfo_children():
            child.destroy()
        today = date.today()
        self.title_label.configure(text=f"{calendar.month_name[self.month]} {self.year}")
        at_limit = not self.allow_future and (self.year, self.month) >= (today.year, today.month)
        self.next_btn.configure(state="disabled" if at_limit else "normal")
        for col, name in enumerate(("Mo", "Tu", "We", "Th", "Fr", "Sa", "Su")):
            tk.Label(self.grid_frame, text=name, background=theme.SURFACE, foreground=theme.MUTED,
                     width=4).grid(row=0, column=col)
        for row, week in enumerate(calendar.Calendar().monthdatescalendar(self.year, self.month), 1):
            for col, day in enumerate(week):
                in_month = day.month == self.month
                blocked = not self.allow_future and day > today
                is_sel = day == self.selected
                bg = theme.STEEL if is_sel else (theme.SELECT if day == today else theme.SURFACE)
                fg = "white" if is_sel else (theme.TEXT if in_month else "#A0A8B2")
                btn = tk.Button(
                    self.grid_frame, text=str(day.day), width=4, relief="flat", bd=0,
                    background=bg, foreground=fg, activebackground=theme.SELECT,
                    disabledforeground="#C9CED5", cursor="hand2",
                    state="disabled" if blocked else "normal",
                    command=lambda d=day: self._pick(d))
                btn.grid(row=row, column=col, padx=1, pady=1)

    def _pick(self, day: date):
        self.on_pick(day)
        self.destroy()


# ------------------------------------------------------------ quantity field ---
_QTY_RE = re.compile(r"^\d{0,10}(\.\d{0,3})?$")


class QtyField(ttk.Entry):
    """Numeric entry (max 3 decimals). With a maximum set, keystrokes that would
    exceed it are refused and `on_limit` is called so the form can explain why."""

    def __init__(self, parent, on_limit: Callable[[float], None] | None = None, **kw):
        self.var = tk.StringVar()
        super().__init__(parent, textvariable=self.var, width=14, **kw)
        self.maximum: float | None = None
        self.on_limit = on_limit
        self._vcmd = (self.register(self._validate), "%P")
        self.configure(validate="key", validatecommand=self._vcmd)

    def _validate(self, proposed: str) -> bool:
        if not _QTY_RE.match(proposed):
            self.bell()
            return False
        if self.maximum is not None and proposed not in ("", "."):
            if float(proposed) > self.maximum + 1e-9:
                self.bell()
                if self.on_limit:
                    self.on_limit(self.maximum)
                return False
        return True

    def value(self) -> float:
        try:
            return round(float(self.var.get()), 3)
        except ValueError:
            return 0.0

    def set_value(self, number: float | None) -> None:
        self.configure(validate="none")
        if not number:
            self.var.set("")
        else:
            text = f"{number:.3f}".rstrip("0").rstrip(".")
            self.var.set(text)
        self.configure(validate="key", validatecommand=self._vcmd)

    def set_maximum(self, maximum: float | None) -> None:
        self.maximum = maximum
        if maximum is not None and self.value() > maximum:
            self.set_value(maximum)


# ------------------------------------------------------ autocomplete combobox ---
class AutoCombobox(ttk.Combobox):
    """Editable combobox whose drop-down list narrows as you type."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._all: list[str] = []
        self.bind("<KeyRelease>", self._filter, add="+")

    def set_choices(self, values: list[str]) -> None:
        self._all = list(values)
        self.configure(values=self._all)

    def _filter(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        text = self.get().strip().lower()
        self.configure(values=[v for v in self._all if text in v.lower()] if text else self._all)


# -------------------------------------------------------------- data table ---
class DataTable(ttk.Frame):
    """Treeview with scrollbars, click-to-sort headings, row striping and row ids.

    columns: list of (heading, width, anchor)  anchor in {"w", "e", "center"}
    """

    def __init__(self, parent, columns: list[tuple[str, int, str]], sort_column: int = 0,
                 descending: bool = False, height: int = 12):
        super().__init__(parent)
        self.headings = [c[0] for c in columns]
        self._ids = [f"c{i}" for i in range(len(columns))]
        self.tree = ttk.Treeview(self, columns=self._ids, show="headings", selectmode="browse",
                                 height=height)
        for i, (heading, width, anchor) in enumerate(columns):
            self.tree.heading(self._ids[i], text=heading, anchor=anchor if anchor != "e" else "e",
                              command=lambda c=i: self.sort_by(c, toggle=True))
            self.tree.column(self._ids[i], width=width, minwidth=50, anchor=anchor, stretch=True)
        vbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        hbar = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.tree.tag_configure("stripe", background=theme.STRIPE)
        self.tree.tag_configure("low", background=theme.LOW_TINT, foreground="#6B4B00")
        self.tree.tag_configure("out", background=theme.OUT_TINT, foreground=theme.DANGER)
        self._keys: dict[str, list] = {}
        self._tags: dict[str, tuple] = {}
        self._sort_col, self._desc = sort_column, descending

    def load(self, rows: list[tuple[str, list, list, tuple]]) -> None:
        """rows: (iid, display_values, sort_keys, tags)"""
        self.tree.delete(*self.tree.get_children())
        self._keys.clear()
        self._tags.clear()
        for iid, values, keys, tags in rows:
            self._keys[iid] = keys
            self._tags[iid] = tags
            self.tree.insert("", "end", iid=iid, values=values)
        self.sort_by(self._sort_col)

    def sort_by(self, column: int, toggle: bool = False) -> None:
        if toggle:
            self._desc = not self._desc if column == self._sort_col else False
        self._sort_col = column

        def key(iid):
            value = self._keys[iid][column]
            return (0, value.lower()) if isinstance(value, str) else (1, value)

        # strings and numbers never share a column, so the (type, value) tuple is safe
        for index, iid in enumerate(sorted(self._keys, key=key, reverse=self._desc)):
            self.tree.move(iid, "", index)
            # status tint replaces the stripe (tag priority varies between Tk versions)
            tags = self._tags[iid] or (("stripe",) if index % 2 else ())
            self.tree.item(iid, tags=tags)
        for i, heading in enumerate(self.headings):
            arrow = (" ▼" if self._desc else " ▲") if i == column else ""
            self.tree.heading(self._ids[i], text=heading + arrow)

    def selected_id(self) -> int | None:
        selection = self.tree.selection()
        return int(selection[0]) if selection else None

    def on_double_click(self, callback: Callable[[], None]) -> None:
        self.tree.bind("<Double-1>", lambda e: callback()
                       if self.tree.identify_region(e.x, e.y) == "cell" else None)

    def row_count(self) -> int:
        return len(self.tree.get_children())


# ------------------------------------------------------------------- tiles ---
class Tile(tk.Frame):
    """Big clickable home-screen action with a coloured edge, bold title and hint."""

    def __init__(self, parent, title: str, hint: str, accent: str, command: Callable[[], None]):
        super().__init__(parent, background=theme.LINE, padx=1, pady=1, cursor="hand2",
                         takefocus=True, highlightthickness=2,
                         highlightbackground=theme.CONCRETE, highlightcolor="#3A6EA5")
        self.command = command
        tk.Frame(self, background=accent, width=8).pack(side="left", fill="y")
        self.inner = tk.Frame(self, background=theme.SURFACE, padx=22, pady=18)
        self.inner.pack(side="left", fill="both", expand=True)
        self.labels = [
            tk.Label(self.inner, text=title, font=FONTS["tile_title"], foreground=theme.STEEL,
                     background=theme.SURFACE, anchor="w"),
            tk.Label(self.inner, text=hint, font=FONTS["tile_hint"], foreground=theme.MUTED,
                     background=theme.SURFACE, anchor="w"),
        ]
        for lab in self.labels:
            lab.pack(fill="x")
        for widget in (self, self.inner, *self.labels):
            widget.bind("<Button-1>", lambda _: self.command())
            widget.bind("<Enter>", lambda _: self._paint(theme.SURFACE_HOVER))
            widget.bind("<Leave>", lambda _: self._paint(theme.SURFACE))
        self.bind("<Return>", lambda _: self.command())
        self.bind("<space>", lambda _: self.command())

    def _paint(self, color: str):
        self.inner.configure(background=color)
        for lab in self.labels:
            lab.configure(background=color)


# -------------------------------------------------------------- sidebar item ---
class NavItem(tk.Frame):
    def __init__(self, parent, text: str, command: Callable[[], None]):
        super().__init__(parent, background=theme.STEEL)
        self.active = False
        self.marker = tk.Frame(self, background=theme.STEEL, width=4)
        self.marker.pack(side="left", fill="y")
        self.button = tk.Button(
            self, text=text, anchor="w", relief="flat", bd=0, highlightthickness=0,
            padx=16, pady=9, font=FONTS["nav"], cursor="hand2",
            background=theme.STEEL, foreground=theme.NAV_TEXT,
            activebackground=theme.STEEL_HOVER, activeforeground="white", command=command)
        self.button.pack(side="left", fill="x", expand=True)
        self.button.bind("<Enter>", lambda _: self._hover(True))
        self.button.bind("<Leave>", lambda _: self._hover(False))

    def _hover(self, on: bool):
        if not self.active:
            self.button.configure(background=theme.STEEL_HOVER if on else theme.STEEL)

    def set_active(self, active: bool):
        self.active = active
        self.marker.configure(background=theme.SAFETY if active else theme.STEEL)
        self.button.configure(
            background=theme.STEEL_ACTIVE if active else theme.STEEL,
            foreground="white" if active else theme.NAV_TEXT,
            font=FONTS["nav_active"] if active else FONTS["nav"])


# ------------------------------------------------------------------ dialogs ---
class Modal(tk.Toplevel):
    """Base class for modal dialogs. Call .show() to wait for the result."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(background=theme.SURFACE)
        # A dialog "transient" to a hidden window is invisible on Windows (first-run setup)
        if parent.winfo_toplevel().winfo_viewable():
            self.transient(parent.winfo_toplevel())
        self.result = None
        self.body = ttk.Frame(self, style="Card.TFrame", padding=20)
        self.body.pack(fill="both", expand=True)
        self.bind("<Escape>", lambda _: self.cancel())
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def cancel(self):
        self.result = None
        self.destroy()

    def show(self):
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        if pw < 50:   # parent not shown yet (first-run dialog): centre on screen
            px, py, pw, ph = 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{px + max((pw - w) // 2, 0)}+{py + max((ph - h) // 3, 0)}")
        self.deiconify()
        self.grab_set()
        self.focus_force()
        self.wait_window(self)
        return self.result
