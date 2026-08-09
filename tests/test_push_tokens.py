"""Push notification token tests (/api/v1/employee/push-token,
/api/v1/admin/push-token) plus the notify_employee/notify_admins wiring in
notifications.py that sends to them. Runs against a real (ephemeral, CI-only)
Postgres database, same as tests/test_admin_api.py.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - these tests need a real (ephemeral) Postgres instance",
)

VALID_TOKEN = "ExponentPushToken[abcDEF123-fake-test-token]"


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
            "VALUES (%s, 'Test Co Push', 'America/Chicago', 20.00, 'weekly_40') RETURNING id",
            (f"testpush{os.getpid()}",),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO admin_users (org_id, username, password_hash) VALUES (%s, 'admin1', %s)",
            (org_id, generate_password_hash("AdminPass123!")),
        )
        emp_id = conn.execute(
            "INSERT INTO employees (org_id, employee_code, name, pin_hash, hourly_rate, worker_type) "
            "VALUES (%s,'E001','Push Employee',%s,20.00,'employee') RETURNING id",
            (org_id, generate_password_hash("1234")),
        ).fetchone()["id"]
        code = conn.execute("SELECT company_code FROM organizations WHERE id=%s", (org_id,)).fetchone()["company_code"]
        conn.commit()

    yield {"org_id": org_id, "company_code": code, "employee_id": emp_id}

    with get_db() as conn:
        conn.execute("DELETE FROM push_tokens WHERE org_id=%s", (org_id,))
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


def _admin_token(app_module, org):
    c = app_module.app.test_client()
    r = c.post(
        "/api/v1/auth/admin/login",
        json={"company_code": org["company_code"], "username": "admin1", "password": "AdminPass123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return c, r.get_json()["access_token"]


def test_employee_register_and_unregister_push_token(app_module, org):
    from models import get_db

    c, token = _employee_token(app_module, org)

    r = c.post("/api/v1/employee/push-token", json={"token": VALID_TOKEN}, headers=_auth_headers(token))
    assert r.status_code == 200

    with get_db() as conn:
        row = conn.execute("SELECT * FROM push_tokens WHERE token=%s", (VALID_TOKEN,)).fetchone()
    assert row is not None
    assert row["subject_type"] == "employee"
    assert row["subject_id"] == org["employee_id"]

    r = c.delete("/api/v1/employee/push-token", json={"token": VALID_TOKEN}, headers=_auth_headers(token))
    assert r.status_code == 200

    with get_db() as conn:
        row = conn.execute("SELECT * FROM push_tokens WHERE token=%s", (VALID_TOKEN,)).fetchone()
    assert row is None


def test_register_rejects_malformed_token(app_module, org):
    c, token = _employee_token(app_module, org)
    r = c.post("/api/v1/employee/push-token", json={"token": "not-a-real-token"}, headers=_auth_headers(token))
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "validation_error"


def test_register_requires_auth(app_module):
    c = app_module.app.test_client()
    r = c.post("/api/v1/employee/push-token", json={"token": VALID_TOKEN})
    assert r.status_code == 401


def test_re_registering_a_token_reassigns_it_to_the_new_subject(app_module, org):
    """A device token registering under a second subject (e.g. a shared
    device: one employee signs out, a different one signs in) should move
    the existing row rather than fail on the UNIQUE(token) constraint."""
    from models import get_db
    from werkzeug.security import generate_password_hash

    with get_db() as conn:
        other_emp_id = conn.execute(
            "INSERT INTO employees (org_id, employee_code, name, pin_hash, hourly_rate, worker_type) "
            "VALUES (%s,'E002','Second Employee',%s,20.00,'employee') RETURNING id",
            (org["org_id"], generate_password_hash("5678")),
        ).fetchone()["id"]
        conn.commit()

    c1, token1 = _employee_token(app_module, org)
    r = c1.post("/api/v1/employee/push-token", json={"token": VALID_TOKEN}, headers=_auth_headers(token1))
    assert r.status_code == 200

    c2 = app_module.app.test_client()
    r = c2.post(
        "/api/v1/auth/employee/login",
        json={"company_code": org["company_code"], "employee_code": "E002", "pin": "5678"},
    )
    token2 = r.get_json()["access_token"]
    r = c2.post("/api/v1/employee/push-token", json={"token": VALID_TOKEN}, headers=_auth_headers(token2))
    assert r.status_code == 200

    with get_db() as conn:
        rows = conn.execute("SELECT * FROM push_tokens WHERE token=%s", (VALID_TOKEN,)).fetchall()
        conn.execute("DELETE FROM employees WHERE id=%s", (other_emp_id,))
        conn.commit()
    assert len(rows) == 1, "re-registering must reassign the existing row, not duplicate it"
    assert rows[0]["subject_id"] == other_emp_id


def test_admin_register_push_token(app_module, org):
    from models import get_db

    c, token = _admin_token(app_module, org)
    r = c.post("/api/v1/admin/push-token", json={"token": VALID_TOKEN}, headers=_auth_headers(token))
    assert r.status_code == 200

    with get_db() as conn:
        row = conn.execute("SELECT * FROM push_tokens WHERE token=%s", (VALID_TOKEN,)).fetchone()
    assert row is not None
    assert row["subject_type"] == "admin"


def test_notify_employee_pushes_to_registered_tokens_and_prunes_stale_ones(app_module, org, monkeypatch):
    """notify_employee (notifications.py) is the single choke point every
    in-app notification (shift claimed, PTO decided, ...) goes through - this
    confirms it actually reaches notify_push.send_push, and that a token
    Expo reports as stale gets removed rather than retried forever."""
    import notifications
    from models import get_db

    sent = {}

    def fake_send_push(tokens, title, body, data=None):
        sent["tokens"] = list(tokens)
        sent["title"] = title
        return [tokens[0]]  # pretend the first token is no longer registered

    monkeypatch.setattr(notifications.notify_push, "send_push", fake_send_push)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO push_tokens (org_id, subject_type, subject_id, token) VALUES (%s,'employee',%s,%s)",
            (org["org_id"], org["employee_id"], VALID_TOKEN),
        )
        conn.commit()

        notifications.notify_employee(
            conn, org["org_id"], org["employee_id"], "test", "Title", body="Body"
        )
        conn.commit()

        remaining = conn.execute(
            "SELECT * FROM push_tokens WHERE subject_type='employee' AND subject_id=%s", (org["employee_id"],)
        ).fetchall()

    assert sent["tokens"] == [VALID_TOKEN]
    assert sent["title"] == "Title"
    assert remaining == [], "the token reported as stale must be pruned"
