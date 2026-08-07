"""Business-critical timekeeping tests: clock-in/out data integrity and
multi-tenant isolation, run against a real (ephemeral, CI-only) Postgres
database with real fixtures - not mocked, not UI-only. Regression coverage
for defects found and fixed during the 2026-08 production QA pass.
"""
import os
import re
import threading
from datetime import timedelta

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - these tests need a real (ephemeral) Postgres instance",
)


def _csrf(resp):
    m = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
    return m.group(1)


@pytest.fixture(scope="module")
def app_module():
    import app as _app
    _app.app.config["TESTING"] = True
    return _app


@pytest.fixture
def two_orgs(app_module):
    """Two isolated companies, each with an admin and one employee, plus a
    disposable third employee for clock-action tests. Created fresh per test
    via direct DB access (bypassing the signup wizard/Stripe entirely -
    that flow is covered elsewhere and isn't what these tests exercise)."""
    from werkzeug.security import generate_password_hash
    from models import get_db

    with get_db() as conn:
        org_a = conn.execute(
            "INSERT INTO organizations (company_code, name, timezone, default_hourly_rate, overtime_rule) "
            "VALUES (%s, 'Test Co A', 'America/Chicago', 20.00, 'weekly_40') RETURNING id",
            (f"testa{os.getpid()}",),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO admin_users (org_id, username, password_hash) VALUES (%s, 'admin_a', %s)",
            (org_a, generate_password_hash("AdminPassA123!")),
        )
        emp_a = conn.execute(
            "INSERT INTO employees (org_id, employee_code, name, pin_hash, hourly_rate, worker_type) "
            "VALUES (%s, 'A001', 'Alice A', %s, 20.00, 'employee') RETURNING id",
            (org_a, generate_password_hash("1234")),
        ).fetchone()["id"]

        org_b = conn.execute(
            "INSERT INTO organizations (company_code, name, timezone, default_hourly_rate, overtime_rule) "
            "VALUES (%s, 'Test Co B', 'America/Chicago', 25.00, 'daily_8') RETURNING id",
            (f"testb{os.getpid()}",),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO admin_users (org_id, username, password_hash) VALUES (%s, 'admin_b', %s)",
            (org_b, generate_password_hash("AdminPassB123!")),
        )
        emp_b = conn.execute(
            "INSERT INTO employees (org_id, employee_code, name, pin_hash, hourly_rate, worker_type) "
            "VALUES (%s, 'B001', 'Bob B', %s, 25.00, 'employee') RETURNING id",
            (org_b, generate_password_hash("5678")),
        ).fetchone()["id"]
        conn.commit()

    yield {"org_a": org_a, "emp_a": emp_a, "org_b": org_b, "emp_b": emp_b}

    with get_db() as conn:
        for eid in (emp_a, emp_b):
            conn.execute("DELETE FROM time_entries WHERE employee_id=%s", (eid,))
        conn.execute("DELETE FROM employees WHERE id IN (%s, %s)", (emp_a, emp_b))
        conn.execute("DELETE FROM admin_users WHERE org_id IN (%s, %s)", (org_a, org_b))
        conn.execute("DELETE FROM organizations WHERE id IN (%s, %s)", (org_a, org_b))
        conn.commit()


def test_concurrent_clock_in_never_creates_two_open_entries(app_module, two_orgs):
    """Regression test: 10 near-simultaneous clock POSTs from one session
    must never leave more than one open entry, and must never fragment a
    single real shift into multiple entries. Reproduced pre-fix as 4 separate
    complete entries from 10 concurrent requests; must be exactly 1 now."""
    from models import get_db

    emp_id, org_id = two_orgs["emp_a"], two_orgs["org_a"]
    c = app_module.app.test_client()
    with c.session_transaction() as sess:
        sess["employee_id"] = emp_id
        sess["org_id"] = org_id
    csrf = _csrf(c.get("/clock"))

    def post():
        c.post("/clock", data={"csrf_token": csrf}, headers={"Referer": "http://localhost/clock"})

    threads = [threading.Thread(target=post) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with get_db() as conn:
        entries = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s", (emp_id,)
        ).fetchall()

    assert len(entries) == 1, f"expected exactly 1 time entry, got {len(entries)}: {entries}"
    assert entries[0]["clock_out"] is None, "the single entry should still be open (clocked in)"


def test_clock_out_after_a_real_delay_still_works(app_module, two_orgs):
    """The debounce added for the above fix must not block a legitimate
    clock-out that happens a reasonable time after clock-in."""
    from models import get_db
    from tz import now_in

    emp_id, org_id = two_orgs["emp_a"], two_orgs["org_a"]
    with get_db() as conn:
        conn.execute(
            "INSERT INTO time_entries (employee_id, clock_in) VALUES (%s, %s)",
            (emp_id, now_in("America/Chicago") - timedelta(minutes=10)),
        )
        conn.commit()

    c = app_module.app.test_client()
    with c.session_transaction() as sess:
        sess["employee_id"] = emp_id
        sess["org_id"] = org_id
    csrf = _csrf(c.get("/clock"))
    c.post("/clock", data={"csrf_token": csrf}, headers={"Referer": "http://localhost/clock"})

    with get_db() as conn:
        entry = conn.execute(
            "SELECT * FROM time_entries WHERE employee_id=%s", (emp_id,)
        ).fetchone()
    assert entry["clock_out"] is not None, "clock-out after a real delay must actually persist"


def test_admin_cannot_edit_another_companys_employee(app_module, two_orgs):
    from models import get_db

    c = app_module.app.test_client()
    r = c.get("/admin/login")
    csrf = _csrf(r)
    org_a = two_orgs["org_a"]
    with get_db() as conn:
        code_a = conn.execute("SELECT company_code FROM organizations WHERE id=%s", (org_a,)).fetchone()["company_code"]

    r = c.post(
        "/admin/login",
        data={"csrf_token": csrf, "company_code": code_a, "username": "admin_a", "password": "AdminPassA123!"},
        follow_redirects=True, headers={"Referer": "http://localhost/admin/login"},
    )
    assert r.status_code == 200

    r = c.get(f"/admin/employees/{two_orgs['emp_b']}/edit")
    assert r.status_code in (302, 403, 404), "cross-tenant employee access must be denied"
    assert b"Bob B" not in r.data


def test_admin_cannot_delete_another_companys_time_entry(app_module, two_orgs):
    from models import get_db

    org_a, emp_b = two_orgs["org_a"], two_orgs["emp_b"]
    with get_db() as conn:
        entry_id = conn.execute(
            "INSERT INTO time_entries (employee_id, clock_in, clock_out) "
            "VALUES (%s, '2026-08-01 09:00', '2026-08-01 17:00') RETURNING id",
            (emp_b,),
        ).fetchone()["id"]
        conn.commit()
        code_a = conn.execute("SELECT company_code FROM organizations WHERE id=%s", (org_a,)).fetchone()["company_code"]

    c = app_module.app.test_client()
    r = c.get("/admin/login")
    csrf = _csrf(r)
    c.post(
        "/admin/login",
        data={"csrf_token": csrf, "company_code": code_a, "username": "admin_a", "password": "AdminPassA123!"},
        follow_redirects=True, headers={"Referer": "http://localhost/admin/login"},
    )
    r = c.get("/admin")
    csrf2 = _csrf(r)
    c.post(
        f"/admin/time-entries/{entry_id}/delete", data={"csrf_token": csrf2},
        follow_redirects=True, headers={"Referer": "http://localhost/admin"},
    )

    with get_db() as conn:
        still_there = conn.execute("SELECT * FROM time_entries WHERE id=%s", (entry_id,)).fetchone()
    assert still_there is not None, "cross-tenant delete must be rejected, not silently succeed"
