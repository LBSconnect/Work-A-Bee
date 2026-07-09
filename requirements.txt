from contextlib import contextmanager

import psycopg2
import psycopg2.extras

import config


class ConnWrapper:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def commit(self):
        self._conn.commit()

    def cursor(self):
        return self._conn.cursor()


@contextmanager
def get_db():
    if not config.DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. On Render this is wired up automatically "
            "via render.yaml; for local dev, set it in your .env file."
        )
    raw_conn = psycopg2.connect(
        config.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        yield ConnWrapper(raw_conn)
        raw_conn.commit()
    except Exception:
        raw_conn.rollback()
        raise
    finally:
        raw_conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                employee_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                hourly_rate REAL NOT NULL,
                worker_type TEXT NOT NULL DEFAULT 'employee',
                active INTEGER NOT NULL DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS time_entries (
                id SERIAL PRIMARY KEY,
                employee_id INTEGER NOT NULL REFERENCES employees(id),
                clock_in TIMESTAMP NOT NULL,
                clock_out TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS report_log (
                id SERIAL PRIMARY KEY,
                report_date DATE UNIQUE NOT NULL,
                sent_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        conn.commit()
