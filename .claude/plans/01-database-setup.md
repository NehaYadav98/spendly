# Plan: Step 1 — Database Setup

## Context
`database/db.py` only contains a comment, and `app.py` has no database connection. Auth, profile and expense features all need a data layer, so this step adds the SQLite helpers and prepares the database at startup, as set out in `.claude/specs/01-database-setup.md`. It adds no routes and leaves the existing ones unchanged.

The app lives one level down from the repo root, so the files to change are `expense-tracker/database/db.py` and `expense-tracker/app.py`.

## Step 0: Save this plan
Plan mode only allows edits to the session plan file. Once approved, copy this plan to `.claude/plans/01-database-setup.md` at the repo root, next to `.claude/specs/`.

## Step 1: `expense-tracker/database/db.py`
Replace the comment with the following, using only `sqlite3`, `datetime.date`, `pathlib.Path` and `werkzeug.security.generate_password_hash`.

**`DB_PATH`**: `Path(__file__).resolve().parent.parent / "expense_tracker.db"`
- The spec allows `spendly.db` or `expense_tracker.db`. `expense_tracker.db` is already in `expense-tracker/.gitignore`, so it can't be committed by accident.
- Building the path from `__file__` means the database doesn't depend on the directory the app is started from.

**`get_db()`**: connect to `DB_PATH`, set `row_factory = sqlite3.Row`, run `PRAGMA foreign_keys = ON`, and return the connection.

**`init_db()`**: run `CREATE TABLE IF NOT EXISTS` for both tables, then close the connection.
- `users`: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `name TEXT NOT NULL`, `email TEXT UNIQUE NOT NULL`, `password_hash TEXT NOT NULL`, `created_at TEXT DEFAULT (datetime('now'))`
- `expenses`: `id INTEGER PRIMARY KEY AUTOINCREMENT`, `user_id INTEGER NOT NULL REFERENCES users(id)`, `amount REAL NOT NULL`, `category TEXT NOT NULL`, `date TEXT NOT NULL`, `description TEXT`, `created_at TEXT DEFAULT (datetime('now'))`
- The parentheses around `datetime('now')` are required by SQLite.

**`seed_db()`**:
1. Return early if `SELECT 1 FROM users LIMIT 1` finds a row.
2. In a single `with conn:` transaction, insert the demo user (`Demo User`, `demo@spendly.com`, hashed `demo123`), take `cursor.lastrowid`, and `executemany` the 8 expenses with `?` placeholders.
3. Close the connection in `finally`.

The single transaction matters: if the user were saved but the expenses failed, the early return would block every later seed and leave the database permanently without expenses.

**Seed data** (amounts in ₹, dates built with `date.today().replace(day=N).isoformat()`; days are 28 or lower, so they're valid in every month):

| Day | Category | Amount | Description |
|---|---|---|---|
| 1 | Food | 450.00 | Groceries |
| 3 | Transport | 120.50 | Auto fare |
| 6 | Bills | 2499.00 | Electricity bill |
| 10 | Health | 850.00 | Pharmacy |
| 14 | Entertainment | 599.00 | Movie tickets |
| 18 | Shopping | 1899.99 | Shoes |
| 22 | Other | 300.00 | Gift wrap and cards |
| 26 | Food | 275.00 | Lunch with friends |

This covers all 7 categories with 8 rows.

## Step 2: `expense-tracker/app.py`
Add the import and the startup calls, with nothing else changed:

```python
from database.db import get_db, init_db, seed_db

app = Flask(__name__)

with app.app_context():
    init_db()
    seed_db()
```

`get_db` will be unused in `app.py` for now, but the spec asks for the import, so it stays.

## Decisions
- **No test file:** the spec says "Files to create: None", so the checks below run from a throwaway script in the scratchpad instead of adding `tests/`.
- **No `CHECK` constraint on `category`:** the spec's schema doesn't include one. The fixed list is only enforced in the seed data for now.
- **No `ON DELETE CASCADE`:** the spec doesn't ask for it. Deleting a user who has expenses will fail until a later step decides otherwise.

## Verification
Run from `expense-tracker/` with `venv/Scripts/python`. No database exists yet, so the first run starts clean.

1. Import `app` twice in separate processes, then confirm `expense_tracker.db` exists next to `app.py`, with exactly 1 user and 8 expenses.
2. Confirm 7 distinct categories, and that all 8 dates are in the current month in `YYYY-MM-DD` format.
3. Confirm the stored hash isn't plaintext and `check_password_hash(hash, "demo123")` returns true.
4. Confirm `get_db()` returns rows with name access (`row["email"]`) and `PRAGMA foreign_keys` returns 1.
5. Confirm a duplicate email and an expense with `user_id=99999` each raise `sqlite3.IntegrityError`, and that counts stay at 1 and 8.
6. Start `python app.py` and confirm it serves `GET /` with a 200 on port 5001 without errors, then stop it.
7. Run `git status` and confirm the `.db` file isn't listed.
8. Read through `db.py` to confirm no SQL uses string formatting.

## Known risks
- **Demo account:** the seed creates a login with a publicly known password whenever `users` is empty, including on any future deployment. That's fine for development, but it needs a guard before going live.
- **Startup side effect:** importing `app` creates and seeds the real database, so future tests that import it will touch `expense_tracker.db` unless the path can be overridden.
- **OneDrive:** the project is in a synced folder, and sync can interfere with SQLite file locks and produce conflict copies. If "database is locked" errors appear, this is the first thing to check.
- **Future dates:** seed dates are spread across the whole month, so some may be later than today. Date-filtered views could treat these as upcoming.
- **Stale `CLAUDE.md` note:** its warning that `database/db.py` is empty will be out of date after this step. The spec doesn't list that file, so it stays unchanged here.
