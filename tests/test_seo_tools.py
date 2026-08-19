"""Smoke coverage for public SEO calculator and sitemap routes."""
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


def test_tools_hub_loads(client):
    resp = client.get("/tools")
    assert resp.status_code == 200
    assert b"Free Workforce Calculators" in resp.data
    assert b"Timecard Calculator" in resp.data
    assert b"Labor Cost Calculator" in resp.data


@pytest.mark.parametrize(
    "slug, heading",
    [
        ("timecard-calculator", b"Free Timecard Calculator"),
        ("overtime-calculator", b"Free Overtime Pay Calculator"),
        ("payroll-hours-calculator", b"Free Payroll Hours Calculator"),
        ("labor-cost-calculator", b"Free Labor Cost Calculator"),
    ],
)
def test_tool_pages_load(client, slug, heading):
    resp = client.get(f"/tools/{slug}")
    assert resp.status_code == 200
    assert heading in resp.data
    assert b"Start Free Trial" in resp.data


def test_unknown_tool_returns_404(client):
    assert client.get("/tools/not-a-real-tool").status_code == 404


def test_tools_sitemap_lists_every_tool(client):
    resp = client.get("/sitemap-tools.xml")
    assert resp.status_code == 200
    assert resp.mimetype == "application/xml"
    for slug in (
        "timecard-calculator",
        "overtime-calculator",
        "payroll-hours-calculator",
        "labor-cost-calculator",
    ):
        assert f"/tools/{slug}".encode() in resp.data


def test_industry_sitemap_is_available_at_advertised_root_url(client):
    resp = client.get("/sitemap-industries.xml")
    assert resp.status_code == 200
    assert resp.mimetype == "application/xml"
    assert b"/industries/construction" in resp.data


def test_robots_advertises_all_public_sitemaps(client):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert b"Sitemap: https://www.workabeez.net/sitemap.xml" in resp.data
    assert b"Sitemap: https://www.workabeez.net/sitemap-industries.xml" in resp.data
    assert b"Sitemap: https://www.workabeez.net/sitemap-tools.xml" in resp.data
