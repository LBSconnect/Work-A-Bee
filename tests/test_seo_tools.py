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
    assert b"Time Tracking ROI Calculator" in resp.data
    assert b"Buddy Punching Cost Calculator" in resp.data
    assert b"Payroll Error Cost Calculator" in resp.data


def test_tools_hub_redesign_has_required_elements(client):
    """Covers the /tools hub redesign: shared header (logo + nav), hero
    copy, the featured-tool CTA route, every calculator route still being
    discoverable from the hub, and the signup/pricing CTAs."""
    from seo_tools import TOOLS

    resp = client.get("/tools")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    # Work-A-Beez logo stays visible in the shared public header.
    assert 'src="/static/logo-workabee.png"' in html
    assert 'alt="Work-A-Beez"' in html

    # Public nav retains Home, Free Tools, and Pricing.
    assert ">Home<" in html
    assert ">Free Tools<" in html
    assert ">Pricing<" in html

    # Hero headline, subheadline, and trust row.
    assert "Free Workforce Calculators for Small Businesses" in html
    assert "Estimate payroll hours, labor cost, timekeeping ROI" in html
    assert "Free to use" in html
    assert "No signup required" in html
    assert "Built for small businesses" in html

    # The ROI calculator is featured and its CTAs point at the real route.
    assert "Featured Tool" in html
    assert 'href="/tools/employee-time-tracking-roi-calculator"' in html
    assert "Try the ROI Calculator" in html
    assert "Calculate My ROI" in html

    # Every existing calculator route is still discoverable from the hub -
    # rendered dynamically from the TOOLS dict, not hardcoded.
    for slug in TOOLS:
        assert f'href="/tools/{slug}"' in html

    # Signup and pricing CTAs are present (product bridge + final CTA).
    assert 'href="/signup"' in html
    assert 'href="/pricing"' in html
    assert "Start Your Free 14-Day Trial" in html


@pytest.mark.parametrize(
    "slug, heading",
    [
        ("timecard-calculator", b"Free Timecard Calculator"),
        ("overtime-calculator", b"Free Overtime Pay Calculator"),
        ("payroll-hours-calculator", b"Free Payroll Hours Calculator"),
        ("labor-cost-calculator", b"Free Labor Cost Calculator"),
        ("employee-time-tracking-roi-calculator", b"Employee Time Tracking ROI Calculator"),
        ("buddy-punching-cost-calculator", b"Buddy Punching Cost Calculator"),
        ("payroll-error-cost-calculator", b"Payroll Error Cost Calculator"),
    ],
)
def test_tool_pages_load(client, slug, heading):
    resp = client.get(f"/tools/{slug}")
    assert resp.status_code == 200
    assert heading in resp.data
    assert b"Start Free Trial" in resp.data


def test_roi_tool_uses_current_plan_source_of_truth(client):
    from plans import PLANS

    resp = client.get("/tools/employee-time-tracking-roi-calculator")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert f"data-starter-max=\"{PLANS['starter']['max_employees']}\"" in html
    assert f"data-starter-price=\"{PLANS['starter']['price']}\"" in html
    assert f"data-growth-max=\"{PLANS['growth']['max_employees']}\"" in html
    assert f"data-growth-price=\"{PLANS['growth']['price']}\"" in html
    assert f"data-business-max=\"{PLANS['business']['max_employees']}\"" in html
    assert f"data-business-price=\"{PLANS['business']['price']}\"" in html
    assert "This is a planning model, not a savings guarantee." in html


def test_buddy_punching_tool_uses_observed_inputs_and_disclaimer(client):
    resp = client.get("/tools/buddy-punching-cost-calculator")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert 'id="buddy-employees"' in html
    assert 'id="buddy-rate"' in html
    assert 'id="buddy-minutes"' in html
    assert 'id="buddy-occurrences"' in html
    assert "does not establish that buddy punching" in html
    assert "calcBuddyPunching()" in html


def test_payroll_error_tool_models_admin_cost_only(client):
    resp = client.get("/tools/payroll-error-cost-calculator")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    assert 'id="payroll-error-count"' in html
    assert 'id="payroll-error-minutes"' in html
    assert 'id="payroll-error-rate"' in html
    assert 'id="payroll-error-periods"' in html
    assert "does not calculate employee underpayments" in html
    assert "calcPayrollErrors()" in html


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
        "employee-time-tracking-roi-calculator",
        "buddy-punching-cost-calculator",
        "payroll-error-cost-calculator",
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
