"""Smoke coverage for public best-fit SEO routes and pricing assertions."""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set - app boot requires a real Postgres instance",
)


@pytest.fixture(scope="module")
def client():
    import app as app_module
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_best_fit_hub_loads(client):
    resp = client.get("/best-for")
    assert resp.status_code == 200
    assert b"Find the Right Employee Time Clock Fit" in resp.data
    assert b"Time Clock for 5 Employees" in resp.data
    assert b"Time Clock for 10 Employees" in resp.data


@pytest.mark.parametrize(
    "slug, heading",
    [
        ("small-business-employee-time-clock", b"Employee Time Clock for Small Business"),
        ("time-clock-for-5-employees", b"Employee Time Clock for a 5-Person Team"),
        ("time-clock-for-10-employees", b"Employee Time Clock for a 10-Person Team"),
        ("time-clock-for-hourly-employees", b"Time Clock Software for Hourly Employees"),
        ("shared-computer-employee-time-clock", b"Use a Shared Computer as Your Employee Time Clock"),
    ],
)
def test_best_fit_pages_load(client, slug, heading):
    resp = client.get(f"/best-for/{slug}")
    assert resp.status_code == 200
    assert heading in resp.data
    assert b"Start Free Trial" in resp.data


def test_current_growth_pricing_is_visible_on_relevant_pages(client):
    for slug in ("small-business-employee-time-clock", "time-clock-for-10-employees", "time-clock-for-hourly-employees", "shared-computer-employee-time-clock"):
        resp = client.get(f"/best-for/{slug}")
        assert b"$79/month" in resp.data


def test_current_business_pricing_is_visible_on_relevant_pages(client):
    for slug in ("small-business-employee-time-clock", "time-clock-for-hourly-employees", "shared-computer-employee-time-clock"):
        resp = client.get(f"/best-for/{slug}")
        assert b"$139.99/month" in resp.data


def test_five_employee_page_matches_starter_limit(client):
    resp = client.get("/best-for/time-clock-for-5-employees")
    assert b"up to 5 employees" in resp.data
    assert b"$0/month" in resp.data


def test_unknown_best_fit_page_returns_404(client):
    assert client.get("/best-for/not-a-real-fit").status_code == 404


def test_best_fit_sitemap_lists_every_page(client):
    resp = client.get("/sitemap-best-fit.xml")
    assert resp.status_code == 200
    assert resp.mimetype == "application/xml"
    for slug in (
        "small-business-employee-time-clock",
        "time-clock-for-5-employees",
        "time-clock-for-10-employees",
        "time-clock-for-hourly-employees",
        "shared-computer-employee-time-clock",
    ):
        assert f"/best-for/{slug}".encode() in resp.data


def test_robots_advertises_best_fit_sitemap(client):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert b"Sitemap: https://www.workabeez.net/sitemap-best-fit.xml" in resp.data
