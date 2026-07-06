import os
import sqlite3


def _db_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'expenses.db'))


def get_db():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_tables():
    conn = get_db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS expenses (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, desc TEXT, amount REAL, category TEXT, user_id INTEGER)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT)"
    )
    conn.commit()
    conn.close()


def get_setting(conn, key, default, user_id=None):
    if user_id is not None:
        composite = f'user:{user_id}:{key}'
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (composite,)).fetchone()
        if row:
            try:
                return float(row[0])
            except ValueError:
                return default

    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        try:
            return float(row[0])
        except ValueError:
            return default

    return default
