from flask import Blueprint, abort, Response, render_template

seo_best_fit_bp = Blueprint("seo_best_fit", __name__)

PAGES = {
    "small-business-employee-time-clock": {
        "label": "Small Business Employee Time Clock",
        "title": "Best Employee Time Clock for Small Business | Work-A-Beez",
        "description": "A browser-based employee time clock built for small businesses that want PIN clock-in, employer-authorized devices, scheduling and payroll-ready time records.",
        "h1": "Employee Time Clock for Small Business",
        "lede": "If your team works from a shop, office, warehouse, counter, or other shared workplace, Work-A-Beez gives you a simple browser-based clock without dedicated hardware or required employee phone apps.",
        "fit": "Best fit for small employers that want a controlled workplace punch point, simple employee PINs, schedules, time records and payroll reporting in one system.",
        "reasons": ["Use computers your business already owns", "PIN-based employee clock-in and clock-out", "Employer-authorized clock-in devices", "Scheduling and attendance records", "Plans from 5 to 100 employees"],
        "plan": "For very small teams, Starter supports up to 5 employees at $0/month. Growth supports up to 10 employees at $79/month, and Business supports up to 100 employees at $139.99/month.",
    },
    "time-clock-for-5-employees": {
        "label": "Time Clock for 5 Employees",
        "title": "Employee Time Clock for 5 Employees | Free Starter Plan | Work-A-Beez",
        "description": "Need a time clock for five employees? Work-A-Beez Starter supports up to 5 employees with an authorized clock-in device, PIN punches, scheduling and reports for $0/month.",
        "h1": "Employee Time Clock for a 5-Person Team",
        "lede": "A five-person team should not need enterprise software or expensive punch-clock hardware just to keep clean time records.",
        "fit": "Best fit for a very small on-site team that needs one shared clock-in point and wants to move away from paper timesheets or spreadsheets.",
        "reasons": ["Starter plan supports up to 5 employees", "$0 monthly Starter price", "One authorized clock-in device", "Employee ID and PIN workflow", "Weekly schedules and payroll reports"],
        "plan": "Starter is $0/month for up to 5 employees and one authorized clock-in device. Every plan is free for the first 14 days under the current public offer.",
    },
    "time-clock-for-10-employees": {
        "label": "Time Clock for 10 Employees",
        "title": "Employee Time Clock for 10 Employees | Work-A-Beez Growth",
        "description": "Time clock software for teams up to 10 employees. Work-A-Beez Growth is $79/month with up to 3 authorized clock-in devices, PIN clock-in and workforce reporting.",
        "h1": "Employee Time Clock for a 10-Person Team",
        "lede": "Once a team grows beyond a handful of employees, manual time tracking can turn into a recurring payroll chore. Work-A-Beez Growth is designed for teams up to ten employees.",
        "fit": "Best fit for small businesses with up to 10 employees that want multiple approved punch points and a consistent timekeeping process.",
        "reasons": ["Growth supports up to 10 employees", "Up to 3 authorized clock-in devices", "PIN-based clock-in", "Overtime rules and automatic lunch deduction settings", "Time-entry correction workflows"],
        "plan": "Growth is $79/month for up to 10 employees and up to 3 authorized clock-in devices. The current public offer includes a 14-day free trial.",
    },
    "time-clock-for-hourly-employees": {
        "label": "Time Clock for Hourly Employees",
        "title": "Employee Time Clock for Hourly Workers | Work-A-Beez",
        "description": "Track hourly employee clock-ins, clock-outs, breaks, schedules and payroll-ready time records with a browser-based PIN time clock on employer-authorized devices.",
        "h1": "Time Clock Software for Hourly Employees",
        "lede": "Hourly teams need reliable punch records that managers can review before payroll. Work-A-Beez keeps the workplace clock, schedules, breaks and time-entry history together.",
        "fit": "Best fit for hourly employees who report to a fixed workplace and can use a shared or company-controlled computer to clock in and out.",
        "reasons": ["Clock-in and clock-out records", "Break tracking", "Employee schedules", "PIN-based identification", "Payroll-ready reporting"],
        "plan": "Work-A-Beez offers Starter at $0/month for up to 5 employees, Growth at $79/month for up to 10 employees, and Business at $139.99/month for up to 100 employees.",
    },
    "shared-computer-employee-time-clock": {
        "label": "Shared Computer Employee Time Clock",
        "title": "Shared Computer Employee Time Clock | Work-A-Beez",
        "description": "Turn a shared workplace computer into an employee time clock. Work-A-Beez supports PIN clock-in on employer-authorized computers without dedicated punch-clock hardware.",
        "h1": "Use a Shared Computer as Your Employee Time Clock",
        "lede": "For teams that start and end shifts at the same location, one shared computer can be a practical punch point instead of requiring every employee to use a personal phone.",
        "fit": "Best fit for front desks, shops, warehouses, offices, retail back rooms and other workplaces where employees can access a company-controlled computer.",
        "reasons": ["No dedicated punch-clock appliance required", "No required employee phone app", "Employer-authorized device control", "PIN-based employee access", "Centralized time records"],
        "plan": "Starter includes one authorized clock-in device. Growth is $79/month and supports up to 3 authorized devices. Business is $139.99/month with unlimited authorized clock-in devices under the current public plan structure.",
    },
}


@seo_best_fit_bp.route("/best-for")
def best_fit_hub():
    return render_template(
        "seo_best_fit.html",
        page=None,
        pages=PAGES,
        canonical="https://www.workabeez.net/best-for",
    )


@seo_best_fit_bp.route("/best-for/<slug>")
def best_fit_page(slug):
    page = PAGES.get(slug)
    if page is None:
        abort(404)
    related = [(key, value["label"]) for key, value in PAGES.items() if key != slug]
    return render_template(
        "seo_best_fit.html",
        page=page,
        slug=slug,
        pages=PAGES,
        related=related,
        canonical=f"https://www.workabeez.net/best-for/{slug}",
    )


@seo_best_fit_bp.route("/sitemap-best-fit.xml")
def best_fit_sitemap():
    urls = ["https://www.workabeez.net/best-for"] + [
        f"https://www.workabeez.net/best-for/{slug}" for slug in PAGES
    ]
    entries = "".join(
        f"<url><loc>{url}</loc><lastmod>2026-08-19</lastmod><changefreq>monthly</changefreq><priority>0.90</priority></url>"
        for url in urls
    )
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}</urlset>'
    return Response(xml, mimetype="application/xml")
