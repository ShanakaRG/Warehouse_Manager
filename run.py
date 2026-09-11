"""Warehouse Manager - runner and system checker.

    python run.py              check the essentials, then start the program
    python run.py --check      full system check (Python, Tkinter, Excel library, database...)
    python run.py --selftest   test the stock rules on a temporary database (safe, no real data)
    python run.py --install    install / update the required libraries
    python run.py --test       developer tests (pytest)
    python run.py --build      build the Windows program (dist/WarehouseManager/WarehouseManager.exe)

Only uses the standard library until the checks pass, so it works on a fresh Python install.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
import sysconfig
import tempfile
import traceback
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

MIN_PYTHON = (3, 9)
REQUIRED = {"openpyxl": "openpyxl"}          # import name -> pip name
PROJECT_FILES = ["main.py", "app/database.py", "app/export.py", "app/ui/main_window.py",
                 "app/ui/entry_form.py", "assets/app.ico", "requirements.txt"]

# ------------------------------------------------------------------ output ---
if sys.platform.startswith("win"):
    os.system("")                           # enables colours in the Windows console
COLOR = sys.stdout.isatty()
GREEN, YELLOW, RED, BOLD, RESET = (("\033[32m", "\033[33m", "\033[31m", "\033[1m", "\033[0m")
                                   if COLOR else ("", "", "", "", ""))
results: list[str] = []


def ok(msg: str) -> None:
    print(f"  {GREEN}[ OK ]{RESET} {msg}")
    results.append("ok")


def warn(msg: str) -> None:
    print(f"  {YELLOW}[WARN]{RESET} {msg}")
    results.append("warn")


def fail(msg: str) -> None:
    print(f"  {RED}[FAIL]{RESET} {msg}")
    results.append("fail")


def title(text: str) -> None:
    print(f"\n{BOLD}{text}{RESET}")


def ask(question: str) -> bool:
    if not sys.stdin.isatty():
        return False
    return input(f"  {question} [y/N]: ").strip().lower() in ("y", "yes")


# ----------------------------------------------------------------- install ---
def pip_install(args: list[str]) -> bool:
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    site_writable = os.access(sysconfig.get_paths()["purelib"], os.W_OK)
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *args]
    if not in_venv and not site_writable:
        cmd.insert(4, "--user")             # no admin rights needed
    print(f"  Running: {' '.join(cmd)}\n")
    return subprocess.call(cmd) == 0


def install_requirements() -> bool:
    title("Installing required libraries")
    if subprocess.call([sys.executable, "-m", "pip", "--version"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        fail("pip is not available. Re-install Python and tick 'pip' in the installer options.")
        return False
    success = pip_install(["-r", str(ROOT / "requirements.txt")])
    importlib.invalidate_caches()
    (ok if success else fail)("Libraries installed" if success else "Installation failed (see above)")
    return success


# ------------------------------------------------------------------ checks ---
def check_python() -> bool:
    version = ".".join(map(str, sys.version_info[:3]))
    bits = "64-bit" if sys.maxsize > 2**32 else "32-bit"
    if sys.version_info < MIN_PYTHON:
        fail(f"Python {version} is too old. Install Python {'.'.join(map(str, MIN_PYTHON))} "
             "or newer from python.org")
        return False
    ok(f"Python {version} ({bits}) at {sys.executable}")
    return True


def check_tkinter(open_window: bool = True) -> bool:
    try:
        import tkinter as tk
    except ImportError:
        fail("Tkinter is missing. Re-install Python from python.org and keep "
             "'tcl/tk and IDLE' ticked.")
        return False
    ok(f"Tkinter available (Tcl/Tk {tk.TkVersion})")
    if not open_window:
        return True
    try:
        root = tk.Tk()
        root.withdraw()
        width, height = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
    except tk.TclError as exc:
        fail(f"Tkinter cannot open a window: {exc}")
        return False
    if width < 1100 or height < 650:
        warn(f"Screen is {width}x{height}. 1366x768 or larger is recommended.")
    else:
        ok(f"A window can be opened (screen {width}x{height})")
    return True


def check_libraries(offer_install: bool = True) -> bool:
    missing = []
    for module, pip_name in REQUIRED.items():
        try:
            mod = importlib.import_module(module)
            ok(f"{module} {getattr(mod, '__version__', '')} installed (Excel export)")
        except ImportError:
            fail(f"{module} is not installed (needed for Excel export)")
            missing.append(pip_name)
    if missing and offer_install and ask("Install the missing libraries now?"):
        if install_requirements():
            return check_libraries(offer_install=False)
    return not missing


def check_project_files() -> bool:
    missing = [f for f in PROJECT_FILES if not (ROOT / f).exists()]
    if missing:
        fail("Program files missing: " + ", ".join(missing))
        return False
    from app.version import __version__
    ok(f"Program files present (Warehouse Manager {__version__})")
    return True


def check_data_folder() -> bool:
    from app.paths import backup_dir, data_dir
    folder = data_dir()
    try:
        probe = folder / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        ok(f"Data folder is writable: {folder}")
    except OSError as exc:
        fail(f"Cannot write to the data folder {folder}: {exc}")
        return False
    free_mb = shutil.disk_usage(folder).free // (1024 * 1024)
    (ok if free_mb > 200 else warn)(f"Free disk space: {free_mb:,} MB")
    backups = sorted(backup_dir().glob("*.db"))
    if backups:
        latest = datetime.fromtimestamp(backups[-1].stat().st_mtime)
        ok(f"{len(backups)} backups, latest {latest:%d/%m/%Y %H:%M}")
    else:
        warn("No backups yet (one is made automatically when the program starts)")
    return True


def check_database() -> bool:
    from app.paths import db_path
    path = db_path()
    if not path.exists():
        warn(f"No database yet. It will be created on first start: {path}")
        return True
    try:
        conn = sqlite3.connect(str(path))
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
    except sqlite3.Error as exc:
        fail(f"Database cannot be read: {exc}")
        return False
    if integrity != "ok":
        fail(f"Database is damaged ({integrity}). Restore the latest backup from the backups folder.")
        return False
    from app.database import Database
    db = Database(path)
    try:
        materials = db.stock_balance()
        entries = db.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        version = db.conn.execute("PRAGMA user_version").fetchone()[0]
        negative = [m["name"] for m in materials if m["balance"] < 0]
        ok(f"Database OK: {len(materials)} materials, {entries} entries "
           f"(schema v{version}, {path.stat().st_size // 1024} KB)")
        if negative:
            fail("Negative balance found for: " + ", ".join(negative))
        else:
            ok("No material has a negative balance")
        ok(f"Company: {db.company_name or '(not set yet)'} | User: {db.username}")
    finally:
        db.close()
    return not negative


def check_excel_export() -> bool:
    try:
        from app.database import Database
        from app.export import export_all
    except ImportError as exc:
        fail(f"Excel export not available: {exc}")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(":memory:")
        try:
            export_all(db, Path(tmp) / "check.xlsx")
            ok("Excel export works")
            return True
        except Exception as exc:  # noqa: BLE001
            fail(f"Excel export failed: {exc}")
            return False
        finally:
            db.close()


def full_check() -> bool:
    title("1. Python")
    good = check_python()
    title("2. Tkinter (windows and buttons)")
    good = check_tkinter() and good
    title("3. Libraries")
    good = check_libraries() and good
    title("4. Program files")
    good = check_project_files() and good
    if good:
        title("5. Data folder and backups")
        good = check_data_folder() and good
        title("6. Database")
        good = check_database() and good
        title("7. Excel export")
        good = check_excel_export() and good
    summary()
    return good


def summary() -> None:
    fails, warns = results.count("fail"), results.count("warn")
    title("Result")
    if fails:
        print(f"  {RED}{fails} problem(s) found.{RESET} Fix the [FAIL] items above.")
    elif warns:
        print(f"  {GREEN}Ready to use{RESET}, with {warns} note(s) above.")
    else:
        print(f"  {GREEN}Everything is ready.{RESET}")


# --------------------------------------------------------------- self-test ---
def self_test() -> bool:
    """Exercises the real stock rules on a temporary in-memory database."""
    title("Self-test: stock rules on a temporary database (your real data is not touched)")
    from app.database import IN, OUT, Database, InsufficientStockError, ValidationError
    db = Database(":memory:")
    db.set_setting("username", "self-test")
    today = date.today()
    passed = True

    def step(name, func):
        nonlocal passed
        try:
            func()
            ok(name)
        except Exception as exc:  # noqa: BLE001
            passed = False
            fail(f"{name}: {exc}")

    def expect_error(func, error=InsufficientStockError):
        try:
            func()
        except error:
            return
        raise AssertionError("was allowed but should have been refused")

    def equal(a, b):
        if abs(a - b) > 1e-9:
            raise AssertionError(f"expected {b}, got {a}")

    def must(condition, message):
        if not condition:
            raise AssertionError(message)

    mid = db.add_material("Test cement", "bag", 10)
    step("Receive 50 -> balance 50",
         lambda: (db.add_transaction(IN, mid, today, 50, "Supplier"), equal(db.get_balance(mid), 50)))
    step("Issuing 51 is refused",
         lambda: expect_error(lambda: db.add_transaction(OUT, mid, today, 51, "Site")))
    step("Issue exactly 50 -> balance 0",
         lambda: (db.add_transaction(OUT, mid, today, 50, "Site"), equal(db.get_balance(mid), 0)))
    step("Issuing from empty stock is refused",
         lambda: expect_error(lambda: db.add_transaction(OUT, mid, today, 1, "Site")))
    first_in = db.list_transactions(txn_type=IN)[0]["id"]
    step("Deleting stock that was already issued is refused",
         lambda: expect_error(lambda: db.delete_transaction(first_in)))
    step("Reducing an incoming entry below what was issued is refused",
         lambda: expect_error(lambda: db.update_transaction(first_in, mid, today, 49, "Supplier")))
    step("Zero and negative quantities are refused",
         lambda: (expect_error(lambda: db.add_transaction(IN, mid, today, 0, "S"), ValidationError),
                  expect_error(lambda: db.add_transaction(IN, mid, today, -5, "S"), ValidationError)))
    step("Decimals add up exactly (0.1 + 0.2 - 0.3 = 0)",
         lambda: (db.add_transaction(IN, mid, today, 0.1, "S"), db.add_transaction(IN, mid, today, 0.2, "S"),
                  db.add_transaction(OUT, mid, today, 0.3, "Site"), equal(db.get_balance(mid), 0)))
    step("Duplicate material names are refused",
         lambda: expect_error(lambda: db.add_material("TEST CEMENT"), ValidationError))
    step("Custom fields are saved",
         lambda: (db.add_transaction(IN, mid, today, 1, "S", extra_fields={"Batch no": "B1"}),
                  must(db.list_transactions(limit=1)[0]["extra_fields"] == {"Batch no": "B1"},
                       "custom fields were not saved")))
    step("Every change is in the change history",
         lambda: must(len(db.list_audit()) == 7, f"expected 7 changes, found {len(db.list_audit())}"))
    try:
        from app.export import export_all
        with tempfile.TemporaryDirectory() as tmp:
            step("Excel export", lambda: export_all(db, Path(tmp) / "t.xlsx"))
    except ImportError:
        warn("Excel export skipped: openpyxl not installed (run: python run.py --install)")
    db.close()
    summary()
    return passed


# ------------------------------------------------------------ dev commands ---
def run_pytest() -> bool:
    title("Developer tests (pytest)")
    if importlib.util.find_spec("pytest") is None:
        if not (ask("pytest is not installed. Install it now?") and pip_install(["pytest"])):
            fail("pytest not installed (python -m pip install pytest)")
            return False
    return subprocess.call([sys.executable, "-m", "pytest", "-q"]) == 0


def build_exe() -> bool:
    title("Building the Windows program with PyInstaller")
    if not (check_python() and check_libraries(offer_install=True)):
        return False
    if importlib.util.find_spec("PyInstaller") is None:
        if not (ask("PyInstaller is not installed. Install it now?") and pip_install(["pyinstaller"])):
            fail("PyInstaller not installed (python -m pip install pyinstaller)")
            return False
    subprocess.check_call([sys.executable, "installer/make_version_info.py"])
    code = subprocess.call([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                            "WarehouseManager.spec"])
    exe = ROOT / "dist" / "WarehouseManager" / ("WarehouseManager.exe" if os.name == "nt"
                                                 else "WarehouseManager")
    if code == 0 and exe.exists():
        ok(f"Built: {exe}")
        print("  To make an installer, open installer/WarehouseManager.iss with Inno Setup "
              "(or push a git tag and let GitHub build it).")
        return True
    fail("Build failed (see messages above)")
    return False


def start_app() -> int:
    title("Checking before start")
    if not (check_python() and check_tkinter(open_window=False) and check_project_files()):
        summary()
        return 1
    if not check_libraries(offer_install=True):
        warn("Starting anyway. Excel export will not work until the library is installed.")
    print("\n  Starting Warehouse Manager... (keep this window open while you use it)\n")
    try:
        import main
        return main.main()
    except Exception:  # noqa: BLE001 - make any start-up crash visible in the console
        traceback.print_exc()
        fail("The program stopped with an error (details above). Run: python run.py --check")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Warehouse Manager runner and system checker")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="full system check")
    group.add_argument("--selftest", action="store_true", help="test stock rules on a temporary database")
    group.add_argument("--install", action="store_true", help="install / update required libraries")
    group.add_argument("--test", action="store_true", help="run developer tests (pytest)")
    group.add_argument("--build", action="store_true", help="build the Windows .exe with PyInstaller")
    args = parser.parse_args()

    print(f"{BOLD}Warehouse Manager - runner{RESET}  ({ROOT})")
    if args.check:
        return 0 if full_check() else 1
    if args.selftest:
        return 0 if self_test() else 1
    if args.install:
        return 0 if install_requirements() else 1
    if args.test:
        return 0 if run_pytest() else 1
    if args.build:
        return 0 if build_exe() else 1
    return start_app()


if __name__ == "__main__":
    sys.exit(main())
