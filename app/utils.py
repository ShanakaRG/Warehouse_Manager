"""Small helpers with no GUI dependency (safe to use in tests)."""
from datetime import datetime

EPS = 1e-9

STATUS_OK = "In stock"
STATUS_LOW = "Low stock"
STATUS_OUT = "Out of stock"


def fmt_qty(value) -> str:
    """1234.500 -> '1,234.5'; 3.0 -> '3'."""
    if value is None:
        return "0"
    text = f"{float(value):,.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def iso_to_display(iso_date: str) -> str:
    """'2026-09-11' -> '11/09/2026'."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso_date or ""


def stock_status(balance: float, min_stock: float) -> str:
    if balance <= EPS:
        return STATUS_OUT
    if min_stock > 0 and balance <= min_stock + EPS:
        return STATUS_LOW
    return STATUS_OK
