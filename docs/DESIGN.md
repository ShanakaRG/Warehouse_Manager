# Warehouse Manager: design document

Version 1.0 · Author: Shanaka Ramesh, Infinite_engineering solution

## 1. Goals

Replace paper or spreadsheet stock books with a program a storekeeper with basic computer
skills can use without training. The two daily jobs, *receiving* and *issuing*, must be one
click away, and the stock balance must always be correct and never negative.

## 2. Technology choices

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.12 | Fast to develop and maintain; large talent pool. |
| GUI | Tkinter / ttk (Python standard library) | Already included with Python, so nothing extra to install and a small build (~35 MB). The few missing pieces (calendar date picker, sortable tables, a quantity box with a maximum, autocomplete) are implemented in `app/ui/widgets.py` without third-party libraries. |
| Storage | SQLite (single file, WAL mode) | Zero setup, transactional (ACID), handles hundreds of thousands of entries easily. |
| Excel | openpyxl (the only external library) | Writes real `.xlsx` with typed dates and numbers, filters and frozen headers. Loaded only when exporting, so the program still starts if it is missing. |
| Running from source | `runner.bat` + `run.py` | Menu for non-technical users; system check and self-test for support. |
| Packaging | PyInstaller (folder build) + Inno Setup | Folder builds start faster and trigger fewer antivirus false positives than one-file builds. Inno Setup gives a standard Windows installer with Start-menu and desktop shortcuts and a clean uninstaller. |
| CI/CD | GitHub Actions | Free Windows runners; tag-to-release automation. |

## 3. Architecture

```
  runner.bat ─► run.py (checks, self-test, install, build) ─► main.py
                                                               │
        ┌──────────────── Tkinter UI layer (app/ui) ──────────────▼───┐
        │ MainWindow ─ sidebar ─ pages: Home, Receive, Issue, Balance, │
        │ Records, Materials, Settings  ·  dialogs: Setup, About, Edit │
        └───────────────┬───────────────────────────────┬──────────────┘
                        │ calls                         │ calls
               ┌────────▼─────────┐            ┌────────▼────────┐
               │ app/database.py  │◄───────────│  app/export.py  │
               │ rules + SQL      │            │  Excel writer   │
               └────────┬─────────┘            └─────────────────┘
                        │
               %APPDATA%\WarehouseManager\warehouse.db  (+ backups\, error.log)
```

The UI never writes SQL and never decides whether stock is sufficient. It asks the database
layer, which raises a `ValidationError` with a user-friendly message when a rule is broken.
This means the rules are tested without a GUI and cannot be bypassed by a future screen.

## 4. Data model

**materials**: `id, name (unique, case-insensitive), unit, min_stock, created_at`

**transactions**: one table for both directions
`id, txn_type ('IN'|'OUT'), material_id, txn_date, quantity (> 0), party_name,
party_details, reference_no, remarks, extra_fields (JSON), created_by, created_at,
updated_by, updated_at`

- One table for IN and OUT keeps the balance a single `SUM(CASE ...)` query and keeps
  editing, searching and exporting uniform.
- `party_name` is the supplier for incoming and the receiver for outgoing.
- `extra_fields` holds the user-defined "Additional details" as a JSON object, so users can add
  new fields without any schema change. Export turns each distinct field name into a column.

**audit_log**: `ts, username, action, entity, entity_id, details`. Every create, update and
delete is recorded and exported as the *Change history* sheet.

**settings**: key/value (`company_name`, `username`).

The schema version is stored in `PRAGMA user_version`; `Database._migrate()` upgrades old
databases step by step, so future versions can add columns safely.

## 5. Business rules

1. `balance(material) = Σ incoming − Σ outgoing`, and it must be ≥ 0 at all times.
2. Adding an outgoing entry: quantity ≤ current balance. The quantity box refuses any keystroke
   that would exceed the available amount and says why ("You can issue at most 35 bag"), and an
   "Issue all available" button fills it in. The database re-checks inside the
   same `BEGIN IMMEDIATE` transaction as the insert, so two PCs sharing a file can't both
   issue the last item.
3. Editing any entry: the change is applied as a delta per material (undo old, apply new) and
   every affected material must stay ≥ 0. This covers moving an entry to another material.
4. Deleting an incoming entry is blocked if its stock has already been issued.
5. Quantities are rounded to 3 decimals and compared with a small tolerance, so 0.1 + 0.2
   can be issued as 0.3.
6. Dates cannot be in the future. A material with entries cannot be deleted.

## 6. Usability decisions for non-technical users

- Two large, colour-coded actions on the home screen: green for receiving, amber for issuing.
  The same colours are used on the form border, save button and quantities throughout.
- Plain-language labels ("Issued to", "Low-stock warning at") and messages that say what to do
  ("Enter the supplier name."), never technical errors.
- Autocomplete for materials, suppliers, receivers and custom field names; supplier details
  are filled in automatically from the last entry for that supplier.
- New materials can be created from the Receive screen by just typing the name.
- Destructive actions ask for confirmation and default to "No".
- The form clears after saving and keeps the date, ready for the next entry.
- Crashes show a friendly message and write details to `error.log` for the developer.
- Sharp text on high-DPI laptops (the program declares DPI awareness to Windows).
- Layout tested at 1366×768, a common office-PC resolution; the entry form scrolls if needed.
- `runner.bat` gives staff a numbered menu and can create a desktop shortcut.

## 7. Roadmap: suggested improvements

Ordered roughly by value to a typical warehouse.

**High value, low effort**
1. **User login and roles.** Storekeeper (enter only), Manager (edit, delete, settings),
   Viewer (balance and export). The audit log already records user names.
2. **Printable documents.** GRN (goods received note), issue note and gate pass as PDF, with
   company name and signature lines.
3. **Barcode / QR support.** USB scanners type like a keyboard, so scanning into the material
   box works with a small lookup change; add label printing per material.
4. **Import from Excel** for opening balances and the material list when moving from an old
   system.
5. **Stock adjustment entries** (damage, loss, stock-take correction) with reason codes, so
   corrections are recorded instead of edited or deleted.
6. **Returns** (return to supplier, return from site) as their own entry types.

**Medium effort**
7. **Stock value.** Unit price on incoming entries; valuation by weighted average or FIFO;
   value columns in the balance report.
8. **Date-aware balance.** "Stock as of date X" report, and optionally blocking a backdated
   issue that would have made stock negative on that date.
9. **Locations.** Multiple warehouses or rack/bin locations, with transfers between them.
10. **Dashboard charts.** Monthly in/out per material, fastest-moving items.
11. **Attachments.** Photo or scan of the delivery note linked to an entry.
12. **Local-language interface** (all labels are plain strings, easy to move into a translation table).
13. **Auto-update check** against GitHub Releases on start-up.

**Larger change**
14. **Multi-PC network use.** SQLite on a shared network drive is unreliable. For several
    PCs, move storage to PostgreSQL (or a small web API). Because all SQL is in
    `database.py`, only that module needs to change.
15. **Code signing certificate** to remove the SmartScreen warning; the workflow has a
    ready-to-enable signing step.
