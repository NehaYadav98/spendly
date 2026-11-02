import hashlib
import secrets
import sqlite3
from datetime import date
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

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

            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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


def create_user(name, email, password):
    """Return the new user's id, or None if the email is already registered."""
    conn = get_db()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate_user(email, password):
    """Return the user row if the credentials match, otherwise None."""
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    finally:
        conn.close()
    # shortcut: unknown emails skip the hash check, so response time can reveal registered emails; add a dummy hash check before going live.
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def _hash_token(token):
    # Only the hash is stored, so a leaked database holds no usable session tokens.
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id):
    """Record a new server-side session and return its token for the cookie."""
    token = secrets.token_urlsafe(32)
    conn = get_db()
    try:
        with conn:
            # Flask rejects session cookies older than 31 days, so these rows can never match again.
            conn.execute("DELETE FROM sessions WHERE created_at < datetime('now', '-31 days')")
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id) VALUES (?, ?)",
                (_hash_token(token), user_id),
            )
    finally:
        conn.close()
    return token


def is_session_active(token, user_id):
    """Return True if this token is a live session belonging to this user."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT 1 FROM sessions WHERE token_hash = ? AND user_id = ?",
            (_hash_token(token), user_id),
        ).fetchone() is not None
    finally:
        conn.close()


def delete_session(token):
    """End a session on the server. Unknown tokens are ignored."""
    conn = get_db()
    try:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Return the user's public fields, or None. Leaves out password_hash on purpose."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def update_user(user_id, name, email):
    """Save a new name and email. Returns False if the email belongs to another user."""
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "UPDATE users SET name = ?, email = ? WHERE id = ?",
                (name, email, user_id),
            )
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_expenses(user_id):
    """Return all of this user's expenses, newest date first, then newest added."""
    conn = get_db()
    try:
        # shortcut: no paging, so a long history makes a long page; add paging if that becomes a problem.
        return conn.execute(
            "SELECT date, description, category, amount FROM expenses "
            "WHERE user_id = ? ORDER BY date DESC, id DESC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def get_spending_by_category(user_id):
    """Return each category this user has spent in with its total, highest first."""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = ? "
            "GROUP BY category ORDER BY ROUND(SUM(amount), 2) DESC, category ASC",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def get_expense_summary(user_id):
    """Return this user's total spend, expense count and highest-spend category."""
    conn = get_db()
    try:
        totals = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count "
            "FROM expenses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        # ROUND stops floating-point noise from breaking a real tie.
        top = conn.execute(
            "SELECT category FROM expenses WHERE user_id = ? GROUP BY category "
            "ORDER BY ROUND(SUM(amount), 2) DESC, category ASC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    return {
        "total": float(totals["total"]),
        "count": totals["count"],
        "top_category": top["category"] if top else None,
    }
