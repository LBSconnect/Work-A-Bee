"""Smoke coverage for public SEO comparison and sitemap routes."""
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


def test_comparison_hub_loads(client):
    resp = client.get("/compare")
    assert resp.status_code == 200
    assert b"Employee Time Clock Comparisons for Small Business" in resp.data
    assert b"Work-A-Beez vs Paper Timesheets" in resp.data
    assert b"Time Clock Without GPS" in resp.data


@pytest.mark.parametrize(
    "slug, heading",
    [
        ("paper-timesheets", b"A Practical Alternative to Paper Timesheets"),
        ("spreadsheet-time-tracking", b"An Alternative to Spreadsheet Employee Time Tracking"),
        ("time-clock-without-gps", b"Employee Time Clock Without Requiring GPS Tracking"),
        ("employee-phone-clock-in", b"An Alternative to Requiring Employee Phones for Clock-In"),
        ("punch-clock-hardware", b"A Browser-Based Alternative to Dedicated Punch Clock Hardware"),
    ],
)
def test_comparison_pages_load(client, slug, heading):
    resp = client.get(f"/compare/{slug}")
    assert resp.status_code == 200
    assert heading in resp.data
    assert b"$79/month" in resp.data
    assert b"$139.99/month" in resp.data
    assert b"Start 14-Day Trial" in resp.data


def test_unknown_comparison_returns_404(client):
    assert client.get("/compare/not-a-real-comparison").status_code == 404


def test_comparison_sitemap_lists_every_page(client):
    resp = client.get("/sitemap-comparisons.xml")
    assert resp.status_code == 200
    assert resp.mimetype == "application/xml"
    for slug in (
        "paper-timesheets",
        "spreadsheet-time-tracking",
        "time-clock-without-gps",
        "employee-phone-clock-in",
        "punch-clock-hardware",
    ):
        assert f"/compare/{slug}".encode() in resp.data


def test_robots_advertises_comparison_sitemap(client):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert b"Sitemap: https://www.workabeez.net/sitemap-comparisons.xml" in resp.data
