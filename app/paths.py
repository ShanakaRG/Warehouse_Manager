"""File-system locations used by the application."""
import os
import sys
from pathlib import Path

APP_DIR_NAME = "WarehouseManager"


def data_dir() -> Path:
    """Per-user writable folder (e.g. C:\\Users\\<name>\\AppData\\Roaming\\WarehouseManager).

    Program Files is read-only for normal users, so the database must never live there.
    """
    base = os.environ.get("APPDATA") or str(Path.home() / ".local" / "share")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "warehouse.db"


def backup_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_path() -> Path:
    return data_dir() / "error.log"


def resource_path(relative: str) -> Path:
    """Locate bundled resources both in development and inside a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base) / relative
