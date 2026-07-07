import os
import sqlite3


def _db_url():
    return os.environ.get('DATABASE_URL', '').strip()


def _db_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'expenses.db'))


def _is_postgres():
    return bool(_db_url())


def get_db():
    if _is_postgres():
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(_db_url())
        conn.cursor_factory = RealDictCursor
        return conn

    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_tables():
    conn = get_db()
    if _is_postgres():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS expenses (id SERIAL PRIMARY KEY, date TEXT, desc TEXT, amount REAL, category TEXT, user_id INTEGER)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE, password TEXT)"
        )
    else:
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


def _row_value(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get('value')
    return row[0]


def get_setting(conn, key, default, user_id=None):
    if user_id is not None:
        composite = f'user:{user_id}:{key}'
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (composite,)).fetchone()
        if row:
            try:
                return float(_row_value(row))
            except (TypeError, ValueError):
                return default

    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        try:
            return float(_row_value(row))
        except (TypeError, ValueError):
            return default

    return default
