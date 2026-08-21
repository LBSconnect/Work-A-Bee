from flask import Blueprint, Response, abort, render_template, request

from plans import PLANS

seo_tools_bp = Blueprint("seo_tools", __name__)

TOOLS = {
    "timecard-calculator": {
        "label": "Timecard Calculator",
        "title": "Free Timecard Calculator | Work-A-Beez",
        "description": "Free weekly timecard calculator. Add daily start, end and break times to estimate total hours, regular hours and overtime hours.",
        "h1": "Free Timecard Calculator",
        "lede": "Calculate a weekly timecard from daily start, end and unpaid break times. Adjust the overtime threshold to match the rule you want to model.",
        "type": "timecard",
        "note": "This calculator is for planning and estimation. Employers are responsible for applying the wage and hour rules that apply to their workers and location.",
    },
    "overtime-calculator": {
        "label": "Overtime Calculator",
        "title": "Free Overtime Pay Calculator | Work-A-Beez",
        "description": "Estimate regular pay, overtime pay and gross wages with a free configurable overtime calculator from Work-A-Beez.",
        "h1": "Free Overtime Pay Calculator",
        "lede": "Estimate gross wages using your hourly rate, regular hours, overtime hours and overtime multiplier.",
        "type": "overtime",
        "note": "This is an estimation tool, not legal or payroll advice. Overtime eligibility and calculation rules vary by worker and jurisdiction.",
    },
    "payroll-hours-calculator": {
        "label": "Payroll Hours Calculator",
        "title": "Free Payroll Hours Calculator | Work-A-Beez",
        "description": "Add employee hours and hourly rates to estimate total payroll hours and gross hourly payroll for a pay period.",
        "h1": "Free Payroll Hours Calculator",
        "lede": "Quickly total hours and estimated gross hourly payroll for a small team before you run payroll.",
        "type": "payroll",
        "note": "Estimates exclude taxes, deductions, reimbursements, benefits and other payroll adjustments unless you account for them separately.",
    },
    "labor-cost-calculator": {
        "label": "Labor Cost Calculator",
        "title": "Free Labor Cost Calculator for Small Business | Work-A-Beez",
        "description": "Estimate weekly and monthly employee labor cost using headcount, average hours, hourly wage and an adjustable payroll burden percentage.",
        "h1": "Free Labor Cost Calculator",
        "lede": "Model direct wages plus an adjustable payroll burden percentage to estimate weekly and monthly labor cost.",
        "type": "labor",
        "note": "Payroll burden varies by business and may include employer taxes, insurance, benefits and other costs. Enter your own percentage for planning purposes.",
    },
    "employee-time-tracking-roi-calculator": {
        "label": "Time Tracking ROI Calculator",
        "title": "Employee Time Tracking ROI Calculator | Work-A-Beez",
        "description": "Estimate the labor value of minutes lost to manual timekeeping and compare the modeled amount with Work-A-Beez plan pricing.",
        "h1": "Employee Time Tracking ROI Calculator",
        "lede": "Model the dollar value of small daily timekeeping differences across your team, then compare that estimate with the Work-A-Beez plan sized for your headcount.",
        "type": "roi",
        "note": "This is a planning model, not a savings guarantee. It estimates the labor value of the minutes you enter. Work-A-Beez does not guarantee that all modeled time will be recovered, prevented or converted into payroll savings.",
    },
    "buddy-punching-cost-calculator": {
        "label": "Buddy Punching Cost Calculator",
        "title": "Buddy Punching Cost Calculator | Work-A-Beez",
        "description": "Estimate the labor value of suspected or observed buddy punching minutes using affected employees, frequency and average hourly wage.",
        "h1": "Buddy Punching Cost Calculator",
        "lede": "Estimate what recurring unauthorized or inaccurate clock ins could represent in labor dollars using your own observed inputs.",
        "type": "buddy",
        "note": "This calculator is an estimation tool. Its output does not establish that buddy punching, time theft or misconduct occurred, and it does not predict savings from Work-A-Beez. Investigate timekeeping concerns using your records and applicable workplace policies.",
    },
    "payroll-error-cost-calculator": {
        "label": "Payroll Error Cost Calculator",
        "title": "Payroll Error Cost Calculator | Work-A-Beez",
        "description": "Estimate the administrative labor cost of recurring payroll corrections using error volume, correction time and staff cost.",
        "h1": "Payroll Error Cost Calculator",
        "lede": "Model how recurring payroll corrections can consume staff time and administrative dollars using your own observed error volume and correction effort.",
        "type": "payroll_error",
        "note": "This is an administrative cost estimate, not payroll, tax, legal or accounting advice. It does not calculate employee underpayments, penalties, taxes or legal exposure and does not guarantee savings from Work-A-Beez.",
    },
}


@seo_tools_bp.after_app_request
def add_free_tools_to_standalone_public_nav(response):
    """Expose /tools in the two standalone public navs without rewriting large templates."""
    if response.status_code != 200 or response.mimetype != "text/html":
        return response

    if request.path == "/":
        marker = '    <a href="/pricing">Pricing</a>\n'
    elif request.path == "/pricing":
        marker = '    <a href="/pricing" class="current">Pricing</a>\n'
    else:
        return response

    html = response.get_data(as_text=True)
    nav_start = html.find('<div class="nav-links">')
    nav_end = html.find("</div>", nav_start)
    if nav_start == -1 or nav_end == -1:
        return response

    nav_html = html[nav_start:nav_end]
    if 'href="/tools"' in nav_html or marker not in nav_html:
        return response

    replacement = marker + '    <a href="/tools">Free Tools</a>\n'
    response.set_data(html[:nav_start] + nav_html.replace(marker, replacement, 1) + html[nav_end:])
    return response


@seo_tools_bp.route("/tools")
def tools_hub():
    return render_template(
        "seo_tools.html",
        page=None,
        tools=TOOLS,
        plans=PLANS,
        canonical="https://www.workabeez.net/tools",
    )


@seo_tools_bp.route("/tools/<slug>")
def tool_page(slug):
    page = TOOLS.get(slug)
    if page is None:
        abort(404)
    related = [(key, value["label"]) for key, value in TOOLS.items() if key != slug]
    return render_template(
        "seo_tools.html",
        page=page,
        slug=slug,
        tools=TOOLS,
        related=related,
        plans=PLANS,
        canonical=f"https://www.workabeez.net/tools/{slug}",
    )


@seo_tools_bp.route("/sitemap-tools.xml")
def tools_sitemap():
    urls = ["https://www.workabeez.net/tools"] + [
        f"https://www.workabeez.net/tools/{slug}" for slug in TOOLS
    ]
    rows = "".join(
        f"<url><loc>{url}</loc><lastmod>2026-08-20</lastmod><changefreq>monthly</changefreq><priority>{'0.90' if url.endswith('/tools') else '0.85'}</priority></url>"
        for url in urls
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'
    return Response(xml, mimetype="application/xml")
