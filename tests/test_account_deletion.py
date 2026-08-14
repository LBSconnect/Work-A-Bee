"""Account-deletion request tests (/api/v1/employee/account-deletion-request).

Satisfies Apple App Store Guideline 5.1.1(v): this app's accounts are
provisioned by an employer admin rather than self-service signup, so
"delete my account" here is a request routed to the org's admins (via the
same notify_admins path every other admin-facing event already uses), not
an automated deletion pipeline. Runs against a real (ephemeral, CI-only)
Postgres database, same as tests/test_push_tokens.py.
"""
import os

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
    from werkzeug.security import generate_password_hash
    from models import get_db

    with get_db() as conn:
        org_id = conn.execute(
            "INSERT INTO organizations (company_code, name, timezone, default_hourly_rate, overtime_rule) "
            "VALUES (%s, 'Test Co Deletion', 'America/Chicago', 20.00, 'weekly_40') RETURNING id",
            (f"testdel{os.getpid()}",),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO admin_users (org_id, username, password_hash) VALUES (%s, 'admin1', %s)",
            (org_id, generate_password_hash("AdminPass123!")),
        )
        emp_id = conn.execute(
            "INSERT INTO employees (org_id, employee_code, name, pin_hash, hourly_rate, worker_type) "
            "VALUES (%s,'E001','Deletion Employee',%s,20.00,'employee') RETURNING id",
            (org_id, generate_password_hash("1234")),
        ).fetchone()["id"]
        code = conn.execute("SELECT company_code FROM organizations WHERE id=%s", (org_id,)).fetchone()["company_code"]
        conn.commit()

    yield {"org_id": org_id, "company_code": code, "employee_id": emp_id}

    with get_db() as conn:
        conn.execute("DELETE FROM api_refresh_tokens WHERE org_id=%s", (org_id,))
        conn.execute(
            "DELETE FROM notifications WHERE employee_id IN (SELECT id FROM employees WHERE org_id=%s) "
            "OR admin_id IN (SELECT id FROM admin_users WHERE org_id=%s)",
            (org_id, org_id),
        )
        conn.execute("DELETE FROM employees WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM admin_users WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM organizations WHERE id=%s", (org_id,))
        conn.commit()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _employee_token(app_module, org):
    c = app_module.app.test_client()
    r = c.post(
        "/api/v1/auth/employee/login",
        json={"company_code": org["company_code"], "employee_code": "E001", "pin": "1234"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return c, r.get_json()["access_token"]


def test_request_requires_auth(app_module):
    c = app_module.app.test_client()
    r = c.post("/api/v1/employee/account-deletion-request")
    assert r.status_code == 401


def test_request_notifies_the_org_admin(app_module, org):
    from models import get_db

    c, token = _employee_token(app_module, org)
    r = c.post("/api/v1/employee/account-deletion-request", headers=_auth_headers(token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["already_requested"] is False

    with get_db() as conn:
        admin_id = conn.execute(
            "SELECT id FROM admin_users WHERE org_id=%s", (org["org_id"],)
        ).fetchone()["id"]
        note = conn.execute(
            "SELECT * FROM notifications WHERE admin_id=%s AND kind='account_deletion_requested'",
            (admin_id,),
        ).fetchone()

    assert note is not None
    assert "Deletion Employee" in note["title"]
    assert note["link"] == f"/admin/employees/{org['employee_id']}/edit"


def test_a_second_request_within_the_window_does_not_duplicate_the_notification(app_module, org):
    from models import get_db

    c, token = _employee_token(app_module, org)
    r1 = c.post("/api/v1/employee/account-deletion-request", headers=_auth_headers(token))
    assert r1.status_code == 200
    assert r1.get_json()["already_requested"] is False

    r2 = c.post("/api/v1/employee/account-deletion-request", headers=_auth_headers(token))
    assert r2.status_code == 200
    assert r2.get_json()["already_requested"] is True

    with get_db() as conn:
        admin_id = conn.execute(
            "SELECT id FROM admin_users WHERE org_id=%s", (org["org_id"],)
        ).fetchone()["id"]
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM notifications WHERE admin_id=%s AND kind='account_deletion_requested'",
            (admin_id,),
        ).fetchone()["c"]

    assert count == 1, "a repeat request within the dedupe window must not create a second notification"
