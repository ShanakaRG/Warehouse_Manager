"""Opens the real Tkinter window and walks through the key flows.
Skipped automatically where no display is available."""
from datetime import date

import pytest

tk = pytest.importorskip("tkinter")

from app.database import IN, Database  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    warnings = []
    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k: warnings.append(a[0]))
    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    from app.ui import theme
    from app.ui.main_window import MainWindow
    theme.setup(root)
    db = Database(tmp_path / "t.db")
    db.set_setting("company_name", "Test Co")
    db.set_setting("username", "Tester")
    mid = db.add_material("Cement", "bag", 5)
    db.add_transaction(IN, mid, date.today(), 10, party_name="Supplier")
    win = MainWindow(root, db)
    root.update()
    yield win, db, mid, warnings
    root.destroy()
    db.close()


def test_every_page_opens(window):
    win, *_ = window
    for key in ("home", "in", "out", "balance", "records", "materials", "settings", "balance_low"):
        win.go(key)
        win.root.update()


def test_typing_more_than_available_is_refused(window):
    win, db, mid, warnings = window
    win.go("out")
    form = win.pages["out"].form
    form.material.set("Cement")
    form._on_material_changed()
    for ch in "25":                       # 2 is fine, 25 > 10 must be refused
        form.qty.insert("end", ch)
    assert form.qty.get() == "2"
    assert "at most 10" in form.limit_label.cget("text")
    form.all_btn.invoke()
    form.party.set("Site 1")
    form.save()
    assert db.get_balance(mid) == 0 and not warnings


def test_quantity_rejects_letters(window):
    win, *_ = window
    qty = win.pages["in"].form.qty
    for ch in "12a.5x":                   # typed one key at a time, like a person
        qty.insert("end", ch)
    assert qty.get() == "12.5"


def test_custom_fields_are_saved(window):
    win, db, _, _ = window
    win.go("in")
    form = win.pages["in"].form
    form.material.set("Cement")
    form.qty.insert(0, "3")
    form.party.set("Supplier")
    form._add_extra_row("Batch no", "B-9")
    form.save()
    latest = db.list_transactions(txn_type=IN, limit=1)[0]
    assert latest["extra_fields"] == {"Batch no": "B-9"} and latest["quantity"] == 3
