"""End-to-end smoke tests using Flask's test client against a real (ephemeral,
CI-only) Postgres database. Requires DATABASE_URL to be set - these are
skipped automatically if it isn't (e.g. a contributor running `pytest`
without a local Postgres available), so this file never breaks a plain
`pytest tests/` run for someone without a database handy.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - smoke tests need a real (ephemeral) Postgres instance",
)


@pytest.fixture(scope="module")
def client():
    import app as app_module
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = True
    with app_module.app.test_client() as c:
        yield c


def test_homepage_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Work-A-Beez" in resp.data


def test_pricing_page_loads(client):
    resp = client.get("/pricing")
    assert resp.status_code == 200
    assert b"Starter" in resp.data and b"Growth" in resp.data and b"Business" in resp.data


def test_staff_login_page_loads(client):
    assert client.get("/staff/login").status_code == 200


def test_admin_login_page_loads(client):
    assert client.get("/admin/login").status_code == 200


def test_signup_entry_redirects_into_wizard(client):
    resp = client.get("/signup", follow_redirects=True)
    assert resp.status_code == 200
    assert b"company" in resp.data.lower() or b"business" in resp.data.lower()


def test_unknown_route_returns_404(client):
    assert client.get("/this-route-does-not-exist-12345").status_code == 404


def test_admin_dashboard_requires_login(client):
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/admin/login" in resp.headers.get("Location", "")


def test_employee_dashboard_requires_login(client):
    resp = client.get("/clock", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/staff/login" in resp.headers.get("Location", "")


def test_system_dashboard_requires_login(client):
    resp = client.get("/system", follow_redirects=False)
    assert resp.status_code in (301, 302)
    assert "/system/login" in resp.headers.get("Location", "")


def test_csrf_protection_rejects_unsigned_post(client):
    """A POST with no csrf_token must be rejected (400), proving CSRFProtect
    is actually wired up and enforced at runtime - not just present in
    templates. Uses /admin/login as a representative CSRF-protected route."""
    resp = client.post("/admin/login", data={"company_code": "x", "username": "x", "password": "x"})
    assert resp.status_code == 400


def test_stripe_webhook_rejects_bad_signature(client):
    """The webhook must reject a request with no/invalid Stripe-Signature
    header, proving signature verification actually runs."""
    resp = client.post("/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "bogus"})
    assert resp.status_code == 400


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"


def test_robots_and_sitemap_serve(client):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert b"Disallow: /system" in robots.data
    assert b"Disallow: /internal" in robots.data
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200


def test_static_assets_are_cacheable(client):
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert "max-age" in resp.headers.get("Cache-Control", "")
