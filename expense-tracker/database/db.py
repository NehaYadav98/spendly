import sqlite3
from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"

# Days stay at 28 or lower so they are valid in every month.
SEED_EXPENSES = [
    (1, 450.00, "Food", "Groceries"),
    (3, 120.50, "Transport", "Auto fare"),
    (6, 2499.00, "Bills", "Electricity bill"),
    (10, 850.00, "Health", "Pharmacy"),
    (14, 599.00, "Entertainment", "Movie tickets"),
    (18, 1899.99, "Shopping", "Shoes"),
    (22, 300.00, "Other", "Gift wrap and cards"),
    (26, 275.00, "Food", "Lunch with friends"),
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return

        today = date.today()
        # One transaction: a partial seed would never be retried because of the check above.
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
            )
            user_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (user_id, amount, category, today.replace(day=day).isoformat(), description)
                    for day, amount, category, description in SEED_EXPENSES
                ],
            )
    finally:
        conn.close()
