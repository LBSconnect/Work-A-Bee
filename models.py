import traceback
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

    # --- Onboarding wizard additions (additive; run in their own transaction so a
    # problem here can never take down the core app - login/clock/dashboard only
    # depend on the tables/columns created above). ---
    try:
        with get_db() as conn:
            conn.execute("""
                ALTER TABLE organizations
                    ADD COLUMN IF NOT EXISTS dba_name TEXT,
                    ADD COLUMN IF NOT EXISTS business_type TEXT,
                    ADD COLUMN IF NOT EXISTS industry TEXT,
                    ADD COLUMN IF NOT EXISTS address_line1 TEXT,
                    ADD COLUMN IF NOT EXISTS city TEXT,
                    ADD COLUMN IF NOT EXISTS state TEXT,
                    ADD COLUMN IF NOT EXISTS zip TEXT,
                    ADD COLUMN IF NOT EXISTS country TEXT,
                    ADD COLUMN IF NOT EXISTS phone TEXT,
                    ADD COLUMN IF NOT EXISTS website TEXT,
                    ADD COLUMN IF NOT EXISTS logo_data BYTEA,
                    ADD COLUMN IF NOT EXISTS logo_mime TEXT,
                    ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'USD',
                    ADD COLUMN IF NOT EXISTS week_starts_on TEXT NOT NULL DEFAULT 'monday',
                    ADD COLUMN IF NOT EXISTS payroll_frequency TEXT NOT NULL DEFAULT 'weekly',
                    ADD COLUMN IF NOT EXISTS default_shift_minutes INTEGER NOT NULL DEFAULT 480,
                    ADD COLUMN IF NOT EXISTS overtime_rule TEXT NOT NULL DEFAULT 'none',
                    ADD COLUMN IF NOT EXISTS overtime_threshold_hours REAL,
                    ADD COLUMN IF NOT EXISTS round_clock_minutes INTEGER NOT NULL DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS auto_lunch_deduction BOOLEAN NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS lunch_duration_minutes INTEGER NOT NULL DEFAULT 30,
                    ADD COLUMN IF NOT EXISTS allow_paid_breaks BOOLEAN NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS allow_employee_specific_rates BOOLEAN NOT NULL DEFAULT TRUE,
                    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMP
            """)
            conn.execute("""
                ALTER TABLE admin_users
                    ADD COLUMN IF NOT EXISTS first_name TEXT,
                    ADD COLUMN IF NOT EXISTS last_name TEXT,
                    ADD COLUMN IF NOT EXISTS job_title TEXT,
                    ADD COLUMN IF NOT EXISTS email TEXT,
                    ADD COLUMN IF NOT EXISTS mobile_phone TEXT,
                    ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP,
                    ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT NOW()
            """)
            conn.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'admin_users_email_key'
                    ) THEN
                        ALTER TABLE admin_users ADD CONSTRAINT admin_users_email_key UNIQUE (email);
                    END IF;
                END $$;
            """)
            conn.execute("""
                ALTER TABLE employees
                    ADD COLUMN IF NOT EXISTS first_name TEXT,
                    ADD COLUMN IF NOT EXISTS last_name TEXT,
                    ADD COLUMN IF NOT EXISTS email TEXT,
                    ADD COLUMN IF NOT EXISTS phone TEXT,
                    ADD COLUMN IF NOT EXISTS department_id INTEGER,
                    ADD COLUMN IF NOT EXISTS job_title TEXT,
                    ADD COLUMN IF NOT EXISTS manager_id INTEGER REFERENCES employees(id),
                    ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'employee'
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS departments (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    name TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (org_id, name)
                )
            """)
            conn.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'employees_department_id_fkey'
                    ) THEN
                        ALTER TABLE employees
                            ADD CONSTRAINT employees_department_id_fkey
                            FOREIGN KEY (department_id) REFERENCES departments(id);
                    END IF;
                END $$;
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS devices (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    device_name TEXT NOT NULL,
                    token_hash TEXT NOT NULL,
                    registered_by_admin_id INTEGER REFERENCES admin_users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMP,
                    last_seen_ip TEXT,
                    status TEXT NOT NULL DEFAULT 'active'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    actor_type TEXT NOT NULL,
                    actor_id INTEGER,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signup_drafts (
                    id SERIAL PRIMARY KEY,
                    draft_token TEXT UNIQUE NOT NULL,
                    data JSONB NOT NULL DEFAULT '{}'::jsonb,
                    current_step INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("""
                ALTER TABLE time_entries
                    ADD COLUMN IF NOT EXISTS is_manual BOOLEAN NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS created_by_admin_id INTEGER REFERENCES admin_users(id)
            """)
            conn.execute("""
                ALTER TABLE organizations
                    ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
                    ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
                    ADD COLUMN IF NOT EXISTS subscription_status TEXT,
                    ADD COLUMN IF NOT EXISTS cancel_at_period_end BOOLEAN NOT NULL DEFAULT FALSE,
                    ADD COLUMN IF NOT EXISTS current_period_end TIMESTAMP
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS shifts (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    employee_id INTEGER NOT NULL REFERENCES employees(id),
                    shift_start TIMESTAMP NOT NULL,
                    shift_end TIMESTAMP NOT NULL,
                    notes TEXT,
                    created_by_admin_id INTEGER REFERENCES admin_users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_by_admin_id INTEGER REFERENCES admin_users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            conn.execute("""
                ALTER TABLE employees
                    ADD COLUMN IF NOT EXISTS pto_balance_hours REAL NOT NULL DEFAULT 0
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pto_requests (
                    id SERIAL PRIMARY KEY,
                    org_id INTEGER NOT NULL REFERENCES organizations(id),
                    employee_id INTEGER NOT NULL REFERENCES employees(id),
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    hours REAL NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    requested_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    reviewed_by_admin_id INTEGER REFERENCES admin_users(id),
                    reviewed_at TIMESTAMP
                )
            """)
            conn.commit()
    except Exception:
        print("WARNING: onboarding-wizard schema migration failed; core app will still run. Traceback:")
        traceback.print_exc()
