"""Warehouse Manager - application entry point.  Start with:  python main.py  (or run.py)"""
from __future__ import annotations

import logging
import sys
import tkinter as tk
import traceback
from datetime import date
from tkinter import messagebox

from app.database import Database
from app.paths import backup_dir, db_path, log_path, resource_path
from app.version import __app_name__, __version__

KEEP_AUTO_BACKUPS = 30


def enable_high_dpi() -> None:
    """Sharp text on Windows laptops with display scaling (otherwise Tk looks blurry)."""
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass


def daily_backup(db: Database) -> None:
    """One automatic backup per day; keeps the newest KEEP_AUTO_BACKUPS files."""
    try:
        folder = backup_dir()
        target = folder / f"auto_{date.today():%Y-%m-%d}.db"
        if not target.exists():
            db.backup_to(target)
        for old in sorted(folder.glob("auto_*.db"))[:-KEEP_AUTO_BACKUPS]:
            old.unlink(missing_ok=True)
    except OSError as exc:
        logging.error("Automatic backup failed: %s", exc)


def set_icon(root: tk.Tk) -> None:
    try:
        if sys.platform.startswith("win"):
            root.iconbitmap(default=str(resource_path("assets/app.ico")))
        else:
            root._icon = tk.PhotoImage(file=str(resource_path("assets/app.png")))  # keep reference
            root.iconphoto(True, root._icon)
    except tk.TclError:
        pass


def install_error_handler(root: tk.Tk) -> None:
    """Show a friendly message instead of silently failing, and log the details."""
    logging.basicConfig(filename=log_path(), level=logging.ERROR,
                        format="%(asctime)s %(levelname)s %(message)s")

    def handle(exc_type, exc, tb):
        details = "".join(traceback.format_exception(exc_type, exc, tb))
        logging.error("Unhandled error (v%s):\n%s", __version__, details)
        print(details, file=sys.stderr)
        messagebox.showerror("Something went wrong",
                             "An unexpected error happened. Your saved data is safe.\n\n"
                             f"Details were written to:\n{log_path()}\n\n"
                             "Please send that file to the developer.", parent=root)

    root.report_callback_exception = handle


def main() -> int:
    enable_high_dpi()
    root = tk.Tk()
    root.withdraw()                       # hidden until set-up is complete
    root.title(__app_name__)
    from app.ui import theme
    theme.setup(root)
    set_icon(root)
    install_error_handler(root)

    try:
        db = Database(db_path())
    except Exception as exc:  # noqa: BLE001 - any start-up failure must reach the user
        messagebox.showerror("Cannot open the database",
                             f"The data file could not be opened:\n{db_path()}\n\n{exc}")
        return 1

    if not db.company_name:
        from app.ui.dialogs import SetupDialog
        if not SetupDialog(root, db, first_run=True).show():
            return 0

    daily_backup(db)
    from app.ui.main_window import MainWindow
    MainWindow(root, db)
    root.deiconify()
    try:
        root.state("zoomed")             # maximised on Windows
    except tk.TclError:
        root.geometry("1360x840")
    root.mainloop()
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
