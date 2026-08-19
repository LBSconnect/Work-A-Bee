from flask import Blueprint, abort, render_template

seo_tools_bp = Blueprint("seo_tools", __name__)

TOOLS = {
    "timecard-calculator": {
        "label": "Timecard Calculator",
        "title": "Free Timecard Calculator | Work-A-Beez",
        "description": "Free weekly timecard calculator. Add daily start, end and break times to estimate total hours, regular hours and overtime hours.",
        "h1": "Free Timecard Calculator",
        "lede": "Calculate a weekly timecard from daily start, end and unpaid break times. Adjust the overtime threshold to match the rule you want to model.",
        "type": "timecard",
        "note": "This calculator is for planning and estimation. Employers are responsible for applying the wage-and-hour rules that apply to their workers and location.",
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
        "lede": "Model direct wages plus an adjustable payroll-burden percentage to estimate weekly and monthly labor cost.",
        "type": "labor",
        "note": "Payroll burden varies by business and may include employer taxes, insurance, benefits and other costs. Enter your own percentage for planning purposes.",
    },
}


@seo_tools_bp.route("/tools")
def tools_hub():
    return render_template(
        "seo_tools.html",
        page=None,
        tools=TOOLS,
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
        canonical=f"https://www.workabeez.net/tools/{slug}",
    )
