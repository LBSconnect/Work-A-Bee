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
            CREATE TABLE IF NOT EXISTS organizations (
                id SERIAL PRIMARY KEY,
                company_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'America/Chicago',
                default_hourly_rate REAL NOT NULL DEFAULT 16.00,
                report_recipients TEXT,
                report_hour INTEGER NOT NULL DEFAULT 17,
                report_minute INTEGER NOT NULL DEFAULT 0,
                report_weekday INTEGER NOT NULL DEFAULT 4,
                plan TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                id SERIAL PRIMARY KEY,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                UNIQUE (org_id, username)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id SERIAL PRIMARY KEY,
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                employee_code TEXT NOT NULL,
                name TEXT NOT NULL,
                pin_hash TEXT NOT NULL,
                hourly_rate REAL NOT NULL,
                worker_type TEXT NOT NULL DEFAULT 'employee',
                active INTEGER NOT NULL DEFAULT 1,
                UNIQUE (org_id, employee_code)
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
                org_id INTEGER NOT NULL REFERENCES organizations(id),
                report_date DATE NOT NULL,
                sent_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (org_id, report_date)
            )
        """)
        conn.commit()
