"""Admin account-deletion request tests
(/api/v1/admin/account-deletion-request).

Satisfies Apple App Store Guideline 5.1.1(v). Unlike employee accounts
(provisioned by an employer admin - see tests/test_account_deletion.py),
admin accounts are created self-service via the web signup wizard, so this
role needs its own in-app deletion path. There's no in-app "admin's admin"
to route the request to, so it goes to config.PLATFORM_SUPPORT_EMAIL instead
(see api/admin/account_deletion.py). Runs against a real (ephemeral, CI-only)
Postgres database, same as tests/test_account_deletion.py.
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
            "VALUES (%s, 'Test Co Admin Deletion', 'America/Chicago', 20.00, 'weekly_40') RETURNING id",
            (f"testadmdel{os.getpid()}",),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO admin_users (org_id, username, password_hash, email) "
            "VALUES (%s, 'admin1', %s, 'admin1@example.com')",
            (org_id, generate_password_hash("AdminPass123!")),
        )
        code = conn.execute("SELECT company_code FROM organizations WHERE id=%s", (org_id,)).fetchone()["company_code"]
        conn.commit()

    yield {"org_id": org_id, "company_code": code}

    with get_db() as conn:
        conn.execute("DELETE FROM api_refresh_tokens WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM notifications WHERE admin_id IN (SELECT id FROM admin_users WHERE org_id=%s)", (org_id,))
        conn.execute("DELETE FROM admin_users WHERE org_id=%s", (org_id,))
        conn.execute("DELETE FROM organizations WHERE id=%s", (org_id,))
        conn.commit()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _admin_token(app_module, org):
    c = app_module.app.test_client()
    r = c.post(
        "/api/v1/auth/admin/login",
        json={"company_code": org["company_code"], "username": "admin1", "password": "AdminPass123!"},
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return c, r.get_json()["access_token"]


def test_request_requires_auth(app_module):
    c = app_module.app.test_client()
    r = c.post("/api/v1/admin/account-deletion-request")
    assert r.status_code == 401


def test_request_records_a_notification_for_the_requesting_admin(app_module, org):
    from models import get_db

    c, token = _admin_token(app_module, org)
    r = c.post("/api/v1/admin/account-deletion-request", headers=_auth_headers(token))
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
    assert "admin1" in note["title"]
    assert "Test Co Admin Deletion" in note["body"]


def test_a_second_request_within_the_window_does_not_duplicate_the_record(app_module, org):
    from models import get_db

    c, token = _admin_token(app_module, org)
    r1 = c.post("/api/v1/admin/account-deletion-request", headers=_auth_headers(token))
    assert r1.status_code == 200
    assert r1.get_json()["already_requested"] is False

    r2 = c.post("/api/v1/admin/account-deletion-request", headers=_auth_headers(token))
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

    assert count == 1, "a repeat request within the dedupe window must not create a second record"


def test_request_does_not_raise_when_platform_support_email_is_unset(app_module, org, monkeypatch):
    # config.PLATFORM_SUPPORT_EMAIL defaults to "" in this test environment
    # (not set in CI's env block) - notify_email.send_email() must no-op
    # gracefully rather than error, same contract as every other best-effort
    # email in this app.
    import config
    monkeypatch.setattr(config, "PLATFORM_SUPPORT_EMAIL", "")

    c, token = _admin_token(app_module, org)
    r = c.post("/api/v1/admin/account-deletion-request", headers=_auth_headers(token))
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
