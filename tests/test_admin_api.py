"""Mobile admin API tests (/api/v1/admin/*): run against a real (ephemeral,
CI-only) Postgres database with real fixtures - not mocked. Covers the
"Today" team-status view and the PTO/punch-correction approve-deny actions
added for the mobile admin app (Phase D).
"""
import os
from datetime import timedelta

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - these tests need a real (ephemeral) Postgres instance",
)


@pytest.fixture(scope="module")
def app_module():
    import app as _app
    _app.app.config["TESTING"] = True
    return _app


@pytest.fixture
def org(app_module):
    """One org with an admin user. Employees/records are created per-test
    and cleaned up alongside the org in teardown."""
    from werkzeug.security import generate_password_hash
    from models import get_db

    with get_db() as conn:
        org_id = conn.execute(
            "INSERT INTO organizations (company_code, name, timezone, default_hourly_rate, overtime_rule) "
            "VALUES (%s, 'Test Co Admin API', 'America/Chicago', 20.00, 'weekly_40') RETURNING id",
            (f"testadm{os.getpid()}",),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO admin_users (org_id, username, password_hash) VALUES (%s, 'admin1', %s)",
            (org_id, generate_password_hash("AdminPass123!")),
        )
        code = conn.execute("SELECT company_code FROM organizations WHERE id=%s", (org_id,)).fetchone()["company_code"]
        conn.commit()

    yield {"org_id": org_id, "company_code": code}

    with get_db() as conn:
        conn.execute("DELETE FROM api_refresh_tokens WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM audit_log WHERE org_id=%s", (org_id,))
        conn.execute(
            "DELETE FROM notifications WHERE employee_id IN (SELECT id FROM employees WHERE org_id=%s)", (org_id,)
        )
        conn.execute("DELETE FROM punch_corrections WHERE org_id=%s", (org_id,))
        conn.execute(
            "DELETE FROM time_entries WHERE employee_id IN (SELECT id FROM employees WHERE org_id=%s)", (org_id,)
        )
        conn.execute(
            "DELETE FROM shifts WHERE employee_id IN (SELECT id FROM employees WHERE org_id=%s)", (org_id,)
        )
        conn.execute("DELETE FROM pto_requests WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM employees WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM admin_users WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM organizations WHERE id=%s", (org_id,))
        conn.commit()


def _admin_token(app_module, org):
    c = app_module.app.test_client()
    r = c.post(
        "/api/v1/auth/admin/login",
        json={"company_code": org["company_code"], "username": "admin1", "password": "AdminPass123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return c, r.get_json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _make_employee(conn, org_id, code, name, pin="1234", pto_balance_hours=40.0):
    from werkzeug.security import generate_password_hash
    return conn.execute(
        "INSERT INTO employees (org_id, employee_code, name, pin_hash, hourly_rate, worker_type, pto_balance_hours) "
        "VALUES (%s,%s,%s,%s,20.00,'employee',%s) RETURNING id",
        (org_id, code, name, generate_password_hash(pin), pto_balance_hours),
    ).fetchone()["id"]


def test_today_shows_clocked_in_and_late_exceptions(app_module, org):
    from models import get_db
    from tz import now_in, today_in

    org_id = org["org_id"]
    with get_db() as conn:
        emp_clocked = _make_employee(conn, org_id, "E001", "Clocked Employee")
        conn.execute(
            "INSERT INTO time_entries (employee_id, clock_in) VALUES (%s, %s)",
            (emp_clocked, now_in("America/Chicago") - timedelta(hours=1)),
        )

        emp_late = _make_employee(conn, org_id, "E002", "Late Employee")
        shift_start = now_in("America/Chicago") - timedelta(hours=2)
        conn.execute(
            "INSERT INTO shifts (org_id, employee_id, shift_start, shift_end) VALUES (%s,%s,%s,%s)",
            (org_id, emp_late, shift_start, shift_start + timedelta(hours=8)),
        )
        conn.execute(
            "INSERT INTO time_entries (employee_id, clock_in, clock_out) VALUES (%s,%s,%s)",
            (emp_late, shift_start + timedelta(minutes=45), shift_start + timedelta(hours=4)),
        )
        conn.commit()

    c, token = _admin_token(app_module, org)
    r = c.get("/api/v1/admin/today", headers=_auth_headers(token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["date"] == today_in("America/Chicago").isoformat()

    clocked_codes = {row["employee_code"] for row in body["clocked_in_now"]}
    assert clocked_codes == {"E001"}

    late_rows = [row for row in body["exceptions"] if row["employee_code"] == "E002"]
    assert len(late_rows) == 1
    assert "Late" in late_rows[0]["flags"]


def test_pto_approve_deducts_balance_and_is_not_double_applied(app_module, org):
    from models import get_db

    org_id = org["org_id"]
    with get_db() as conn:
        emp = _make_employee(conn, org_id, "E010", "PTO Employee", pto_balance_hours=40.0)
        req_id = conn.execute(
            "INSERT INTO pto_requests (org_id, employee_id, start_date, end_date, hours, reason) "
            "VALUES (%s,%s,'2026-09-01','2026-09-01',8,'Trip') RETURNING id",
            (org_id, emp),
        ).fetchone()["id"]
        conn.commit()

    c, token = _admin_token(app_module, org)

    r = c.get("/api/v1/admin/pto", headers=_auth_headers(token))
    assert r.status_code == 200
    assert any(row["id"] == req_id and row["status"] == "pending" for row in r.get_json()["requests"])

    r = c.post(f"/api/v1/admin/pto/{req_id}/approve", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.get_json()["request"]["status"] == "approved"

    with get_db() as conn:
        balance = conn.execute("SELECT pto_balance_hours FROM employees WHERE id=%s", (emp,)).fetchone()["pto_balance_hours"]
        status = conn.execute("SELECT status FROM pto_requests WHERE id=%s", (req_id,)).fetchone()["status"]
    assert balance == 32.0, "approving an 8h request against a 40h balance must leave exactly 32h"
    assert status == "approved"

    # Replaying the approval must not deduct a second time.
    r = c.post(f"/api/v1/admin/pto/{req_id}/approve", headers=_auth_headers(token))
    assert r.status_code == 404

    with get_db() as conn:
        balance_after_replay = conn.execute(
            "SELECT pto_balance_hours FROM employees WHERE id=%s", (emp,)
        ).fetchone()["pto_balance_hours"]
    assert balance_after_replay == 32.0, "no double-deduction on a replayed approve"


def test_pto_deny_leaves_balance_untouched(app_module, org):
    from models import get_db

    org_id = org["org_id"]
    with get_db() as conn:
        emp = _make_employee(conn, org_id, "E011", "Denied Employee", pto_balance_hours=40.0)
        req_id = conn.execute(
            "INSERT INTO pto_requests (org_id, employee_id, start_date, end_date, hours, reason) "
            "VALUES (%s,%s,'2026-09-02','2026-09-02',8,'Trip') RETURNING id",
            (org_id, emp),
        ).fetchone()["id"]
        conn.commit()

    c, token = _admin_token(app_module, org)
    r = c.post(f"/api/v1/admin/pto/{req_id}/deny", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.get_json()["request"]["status"] == "denied"

    with get_db() as conn:
        balance = conn.execute("SELECT pto_balance_hours FROM employees WHERE id=%s", (emp,)).fetchone()["pto_balance_hours"]
    assert balance == 40.0


def test_correction_approve_writes_clock_out_onto_real_entry(app_module, org):
    from models import get_db

    org_id = org["org_id"]
    with get_db() as conn:
        emp = _make_employee(conn, org_id, "E020", "Correction Employee")
        entry_id = conn.execute(
            "INSERT INTO time_entries (employee_id, clock_in) VALUES (%s, '2026-08-01 09:00') RETURNING id",
            (emp,),
        ).fetchone()["id"]
        correction_id = conn.execute(
            "INSERT INTO punch_corrections (org_id, employee_id, time_entry_id, issue_type, issue_date, "
            "requested_clock_in, requested_clock_out, reason) "
            "VALUES (%s,%s,%s,'missing_clock_out','2026-08-01','2026-08-01 09:00','2026-08-01 17:00','Forgot') "
            "RETURNING id",
            (org_id, emp, entry_id),
        ).fetchone()["id"]
        conn.commit()

    c, token = _admin_token(app_module, org)

    r = c.get("/api/v1/admin/corrections", headers=_auth_headers(token))
    assert r.status_code == 200
    assert any(row["id"] == correction_id for row in r.get_json()["requests"])

    r = c.post(f"/api/v1/admin/corrections/{correction_id}/approve", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.get_json()["request"]["status"] == "approved"

    with get_db() as conn:
        entry = conn.execute("SELECT * FROM time_entries WHERE id=%s", (entry_id,)).fetchone()
    assert entry["clock_out"] is not None, "approving must write clock_out onto the real time_entries row"
    assert entry["is_manual"] is True


def test_correction_deny_requires_comment(app_module, org):
    from models import get_db

    org_id = org["org_id"]
    with get_db() as conn:
        emp = _make_employee(conn, org_id, "E021", "Denied Correction Employee")
        entry_id = conn.execute(
            "INSERT INTO time_entries (employee_id, clock_in) VALUES (%s, '2026-08-02 09:00') RETURNING id",
            (emp,),
        ).fetchone()["id"]
        correction_id = conn.execute(
            "INSERT INTO punch_corrections (org_id, employee_id, time_entry_id, issue_type, issue_date, "
            "requested_clock_in, requested_clock_out, reason) "
            "VALUES (%s,%s,%s,'missing_clock_out','2026-08-02','2026-08-02 09:00','2026-08-02 17:00','Forgot') "
            "RETURNING id",
            (org_id, emp, entry_id),
        ).fetchone()["id"]
        conn.commit()

    c, token = _admin_token(app_module, org)

    r = c.post(f"/api/v1/admin/corrections/{correction_id}/deny", headers=_auth_headers(token), json={})
    assert r.status_code == 422, "a deny with no comment must be rejected"

    r = c.post(
        f"/api/v1/admin/corrections/{correction_id}/deny", headers=_auth_headers(token),
        json={"comment": "Times don't match the schedule."},
    )
    assert r.status_code == 200
    assert r.get_json()["request"]["status"] == "denied"

    with get_db() as conn:
        row = conn.execute("SELECT * FROM punch_corrections WHERE id=%s", (correction_id,)).fetchone()
    assert row["manager_comment"] == "Times don't match the schedule."
    assert row["status"] == "denied"
