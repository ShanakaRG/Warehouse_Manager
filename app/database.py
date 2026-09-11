"""Data access and business rules.

All stock rules live here, not in the UI, so that no screen (current or future)
can ever bypass them:

* Quantities are always > 0; the entry type (IN / OUT) decides the direction.
* A material's balance = total IN - total OUT and can NEVER drop below zero.
  This is checked when adding an outgoing entry, and also when editing or
  deleting ANY entry (e.g. deleting an incoming entry that was already issued).
* Every create / update / delete is written to an audit log.
* Each write runs inside a BEGIN IMMEDIATE transaction so the balance check and
  the write are atomic, even if two copies of the program share one database.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from .utils import EPS, fmt_qty, stock_status

IN = "IN"
OUT = "OUT"
QTY_DECIMALS = 3

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS materials (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    unit       TEXT NOT NULL DEFAULT 'pcs',
    min_stock  REAL NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    txn_type      TEXT NOT NULL CHECK (txn_type IN ('IN', 'OUT')),
    material_id   INTEGER NOT NULL REFERENCES materials(id) ON DELETE RESTRICT,
    txn_date      TEXT NOT NULL,
    quantity      REAL NOT NULL CHECK (quantity > 0),
    party_name    TEXT NOT NULL DEFAULT '',
    party_details TEXT NOT NULL DEFAULT '',
    reference_no  TEXT NOT NULL DEFAULT '',
    remarks       TEXT NOT NULL DEFAULT '',
    extra_fields  TEXT NOT NULL DEFAULT '{}',
    created_by    TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_by    TEXT,
    updated_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_txn_material ON transactions(material_id);
CREATE INDEX IF NOT EXISTS idx_txn_date     ON transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_txn_type     ON transactions(txn_type);

CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT NOT NULL,
    username  TEXT NOT NULL,
    action    TEXT NOT NULL,
    entity    TEXT NOT NULL,
    entity_id INTEGER,
    details   TEXT NOT NULL DEFAULT ''
);
"""

BALANCE_SQL = """
SELECT m.id, m.name, m.unit, m.min_stock,
       COALESCE(SUM(CASE WHEN t.txn_type = 'IN'  THEN t.quantity END), 0) AS total_in,
       COALESCE(SUM(CASE WHEN t.txn_type = 'OUT' THEN t.quantity END), 0) AS total_out,
       COUNT(t.id) AS entry_count
FROM materials m
LEFT JOIN transactions t ON t.material_id = m.id
"""

TXN_SELECT = """
SELECT t.*, m.name AS material_name, m.unit AS unit
FROM transactions t
JOIN materials m ON m.id = t.material_id
"""


class ValidationError(Exception):
    """A problem the user can fix. The message is shown to the user as-is."""


class InsufficientStockError(ValidationError):
    """The change would make a material's balance negative."""


# ----------------------------------------------------------------- cleaning ---
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean_text(value, max_len: int = 500) -> str:
    return str(value or "").strip()[:max_len]


def _clean_qty(value) -> float:
    try:
        qty = round(float(value), QTY_DECIMALS)
    except (TypeError, ValueError):
        raise ValidationError("Quantity must be a number.") from None
    if qty <= 0:
        raise ValidationError("Quantity must be greater than zero.")
    return qty


def _clean_date(value) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValidationError("Date must be a valid date.") from None


def _clean_extra(extra) -> str:
    if not extra:
        return "{}"
    cleaned = {}
    for key, val in dict(extra).items():
        key = _clean_text(key, 60)
        if key:
            cleaned[key] = _clean_text(val)
    return json.dumps(cleaned, ensure_ascii=False)


def _parse_extra(text: str) -> dict:
    try:
        data = json.loads(text or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError):
        return {}


# ----------------------------------------------------------------- database ---
class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        # isolation_level=None -> we control transactions explicitly with _tx().
        self.conn = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def _tx(self):
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        else:
            self.conn.execute("COMMIT")

    def _migrate(self) -> None:
        """Versioned schema upgrades. Add `if version < 2: ...` blocks for future changes."""
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self.conn.executescript(SCHEMA_V1)
            self.conn.execute("PRAGMA user_version = 1")

    # ------------------------------------------------------------ settings ---
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    @property
    def username(self) -> str:
        return self.get_setting("username") or "user"

    @property
    def company_name(self) -> str:
        return self.get_setting("company_name")

    # --------------------------------------------------------------- audit ---
    def _audit(self, action: str, entity: str, entity_id, details: str) -> None:
        self.conn.execute(
            "INSERT INTO audit_log(ts, username, action, entity, entity_id, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), self.username, action, entity, entity_id, details),
        )

    def list_audit(self, limit: int = 5000) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ----------------------------------------------------------- materials ---
    def stock_balance(self) -> list[dict]:
        """Every material with total in / total out / balance / status."""
        rows = self.conn.execute(
            BALANCE_SQL + " GROUP BY m.id ORDER BY m.name COLLATE NOCASE"
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["total_in"] = round(item["total_in"], QTY_DECIMALS)
            item["total_out"] = round(item["total_out"], QTY_DECIMALS)
            item["balance"] = round(item["total_in"] - item["total_out"], QTY_DECIMALS)
            item["status"] = stock_status(item["balance"], item["min_stock"])
            result.append(item)
        return result

    list_materials = stock_balance

    def get_material(self, material_id: int) -> dict | None:
        row = self.conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
        return dict(row) if row else None

    def find_material(self, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM materials WHERE name = ? COLLATE NOCASE", (_clean_text(name),)
        ).fetchone()
        return dict(row) if row else None

    def _validate_material(self, name, unit, min_stock):
        name = _clean_text(name, 120)
        if not name:
            raise ValidationError("Material name is required.")
        unit = _clean_text(unit, 20) or "pcs"
        try:
            min_stock = round(float(min_stock or 0), QTY_DECIMALS)
        except (TypeError, ValueError):
            raise ValidationError("Minimum stock must be a number.") from None
        if min_stock < 0:
            raise ValidationError("Minimum stock cannot be negative.")
        return name, unit, min_stock

    def add_material(self, name: str, unit: str = "pcs", min_stock: float = 0) -> int:
        name, unit, min_stock = self._validate_material(name, unit, min_stock)
        try:
            with self._tx():
                cur = self.conn.execute(
                    "INSERT INTO materials(name, unit, min_stock, created_at) VALUES (?, ?, ?, ?)",
                    (name, unit, min_stock, _now()),
                )
                self._audit("CREATE", "material", cur.lastrowid, f"{name} ({unit})")
                return cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValidationError(f"A material named '{name}' already exists.") from None

    def update_material(self, material_id: int, name: str, unit: str, min_stock: float) -> None:
        name, unit, min_stock = self._validate_material(name, unit, min_stock)
        try:
            with self._tx():
                old = self.get_material(material_id)
                if not old:
                    raise ValidationError("Material not found.")
                self.conn.execute(
                    "UPDATE materials SET name = ?, unit = ?, min_stock = ? WHERE id = ?",
                    (name, unit, min_stock, material_id),
                )
                self._audit("UPDATE", "material", material_id,
                            f"{old['name']} ({old['unit']}, min {fmt_qty(old['min_stock'])}) -> "
                            f"{name} ({unit}, min {fmt_qty(min_stock)})")
        except sqlite3.IntegrityError:
            raise ValidationError(f"A material named '{name}' already exists.") from None

    def delete_material(self, material_id: int) -> None:
        with self._tx():
            material = self.get_material(material_id)
            if not material:
                return
            count = self.conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE material_id = ?", (material_id,)
            ).fetchone()[0]
            if count:
                raise ValidationError(
                    f"'{material['name']}' has {count} entries and cannot be deleted.\n\n"
                    "Delete or move those entries first."
                )
            self.conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))
            self._audit("DELETE", "material", material_id, material["name"])

    # ------------------------------------------------------------- balance ---
    def get_balance(self, material_id: int) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(CASE WHEN txn_type = 'IN' THEN quantity ELSE -quantity END), 0) "
            "FROM transactions WHERE material_id = ?",
            (material_id,),
        ).fetchone()
        return round(row[0], QTY_DECIMALS)

    def _ensure_non_negative(self, deltas: dict[int, float]) -> None:
        """Raise if applying `deltas` (material_id -> change) makes any balance negative."""
        for material_id, delta in deltas.items():
            if delta >= -EPS:
                continue  # adding stock can never break the rule
            current = self.get_balance(material_id)
            after = round(current + delta, QTY_DECIMALS)
            if after < -EPS:
                m = self.get_material(material_id) or {"name": "?", "unit": ""}
                raise InsufficientStockError(
                    f"Not enough stock of '{m['name']}'.\n\n"
                    f"Available now: {fmt_qty(current)} {m['unit']}\n"
                    f"After this change it would be: {fmt_qty(after)} {m['unit']}\n\n"
                    "Stock balance cannot go below zero."
                )

    # -------------------------------------------------------- transactions ---
    def _txn_values(self, material_id, txn_date, quantity, party_name, party_details,
                    reference_no, remarks, extra_fields):
        if self.get_material(material_id) is None:
            raise ValidationError("Please select a valid material.")
        return (
            _clean_date(txn_date),
            _clean_qty(quantity),
            _clean_text(party_name, 150),
            _clean_text(party_details),
            _clean_text(reference_no, 100),
            _clean_text(remarks, 2000),
            _clean_extra(extra_fields),
        )

    def add_transaction(self, txn_type: str, material_id: int, txn_date, quantity,
                        party_name: str = "", party_details: str = "", reference_no: str = "",
                        remarks: str = "", extra_fields: dict | None = None) -> int:
        if txn_type not in (IN, OUT):
            raise ValidationError("Invalid entry type.")
        with self._tx():
            d, q, pn, pd, ref, rem, extra = self._txn_values(
                material_id, txn_date, quantity, party_name, party_details,
                reference_no, remarks, extra_fields)
            if txn_type == OUT:
                self._ensure_non_negative({material_id: -q})
            cur = self.conn.execute(
                "INSERT INTO transactions(txn_type, material_id, txn_date, quantity, party_name, "
                "party_details, reference_no, remarks, extra_fields, created_by, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (txn_type, material_id, d, q, pn, pd, ref, rem, extra, self.username, _now()),
            )
            name = self.get_material(material_id)["name"]
            self._audit("CREATE", "transaction", cur.lastrowid,
                        f"{txn_type} {fmt_qty(q)} x {name} on {d} ({pn})")
            return cur.lastrowid

    def update_transaction(self, txn_id: int, material_id: int, txn_date, quantity,
                           party_name: str = "", party_details: str = "", reference_no: str = "",
                           remarks: str = "", extra_fields: dict | None = None) -> None:
        with self._tx():
            old = self.get_transaction(txn_id)
            if not old:
                raise ValidationError("Entry not found. It may have been deleted.")
            d, q, pn, pd, ref, rem, extra = self._txn_values(
                material_id, txn_date, quantity, party_name, party_details,
                reference_no, remarks, extra_fields)
            sign = 1 if old["txn_type"] == IN else -1
            deltas: dict[int, float] = defaultdict(float)
            deltas[old["material_id"]] -= sign * old["quantity"]   # undo old entry
            deltas[material_id] += sign * q                        # apply new entry
            self._ensure_non_negative(deltas)
            self.conn.execute(
                "UPDATE transactions SET material_id = ?, txn_date = ?, quantity = ?, "
                "party_name = ?, party_details = ?, reference_no = ?, remarks = ?, "
                "extra_fields = ?, updated_by = ?, updated_at = ? WHERE id = ?",
                (material_id, d, q, pn, pd, ref, rem, extra, self.username, _now(), txn_id),
            )
            new_name = self.get_material(material_id)["name"]
            self._audit("UPDATE", "transaction", txn_id,
                        f"{old['txn_type']}: {fmt_qty(old['quantity'])} x {old['material_name']} "
                        f"on {old['txn_date']} -> {fmt_qty(q)} x {new_name} on {d}")

    def delete_transaction(self, txn_id: int) -> None:
        with self._tx():
            old = self.get_transaction(txn_id)
            if not old:
                return
            sign = 1 if old["txn_type"] == IN else -1
            self._ensure_non_negative({old["material_id"]: -sign * old["quantity"]})
            self.conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))
            self._audit("DELETE", "transaction", txn_id,
                        f"{old['txn_type']} {fmt_qty(old['quantity'])} x {old['material_name']} "
                        f"on {old['txn_date']} ({old['party_name']})")

    @staticmethod
    def _row_to_txn(row) -> dict:
        item = dict(row)
        item["extra_fields"] = _parse_extra(item.get("extra_fields"))
        return item

    def get_transaction(self, txn_id: int) -> dict | None:
        row = self.conn.execute(TXN_SELECT + " WHERE t.id = ?", (txn_id,)).fetchone()
        return self._row_to_txn(row) if row else None

    def list_transactions(self, txn_type: str | None = None, material_id: int | None = None,
                          date_from=None, date_to=None, search: str = "",
                          limit: int | None = None) -> list[dict]:
        sql = TXN_SELECT + " WHERE 1 = 1"
        params: list = []
        if txn_type:
            sql += " AND t.txn_type = ?"
            params.append(txn_type)
        if material_id:
            sql += " AND t.material_id = ?"
            params.append(material_id)
        if date_from:
            sql += " AND t.txn_date >= ?"
            params.append(_clean_date(date_from))
        if date_to:
            sql += " AND t.txn_date <= ?"
            params.append(_clean_date(date_to))
        search = _clean_text(search, 100)
        if search:
            like = f"%{search}%"
            sql += (" AND (m.name LIKE ? OR t.party_name LIKE ? OR t.party_details LIKE ? "
                    "OR t.reference_no LIKE ? OR t.remarks LIKE ? OR t.extra_fields LIKE ?)")
            params.extend([like] * 6)
        sql += " ORDER BY t.txn_date DESC, t.id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        return [self._row_to_txn(r) for r in self.conn.execute(sql, params)]

    # ----------------------------------------------------- autocomplete aids ---
    def party_names(self, txn_type: str) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT party_name FROM transactions WHERE txn_type = ? AND party_name <> '' "
            "ORDER BY party_name COLLATE NOCASE", (txn_type,)
        ).fetchall()
        return [r[0] for r in rows]

    def last_party_details(self, txn_type: str, party_name: str) -> str:
        row = self.conn.execute(
            "SELECT party_details FROM transactions WHERE txn_type = ? AND party_name = ? "
            "COLLATE NOCASE AND party_details <> '' ORDER BY id DESC LIMIT 1",
            (txn_type, _clean_text(party_name)),
        ).fetchone()
        return row[0] if row else ""

    def extra_field_names(self) -> list[str]:
        names: set[str] = set()
        for (text,) in self.conn.execute(
            "SELECT DISTINCT extra_fields FROM transactions WHERE extra_fields <> '{}'"
        ):
            names.update(_parse_extra(text).keys())
        return sorted(names, key=str.lower)

    # ---------------------------------------------------------- dashboard ---
    def dashboard_stats(self) -> dict:
        balances = self.stock_balance()
        today = date.today().isoformat()
        counts = dict(self.conn.execute(
            "SELECT txn_type, COUNT(*) FROM transactions WHERE txn_date = ? GROUP BY txn_type",
            (today,),
        ).fetchall())
        return {
            "materials": len(balances),
            "low": sum(1 for b in balances if b["status"] == "Low stock"),
            "out": sum(1 for b in balances if b["status"] == "Out of stock" and b["entry_count"]),
            "today_in": counts.get(IN, 0),
            "today_out": counts.get(OUT, 0),
        }

    # -------------------------------------------------------------- backup ---
    def backup_to(self, destination: str | Path) -> None:
        """Consistent online backup (safe with WAL mode, unlike copying the file)."""
        dest = sqlite3.connect(str(destination))
        try:
            self.conn.backup(dest)
        finally:
            dest.close()
