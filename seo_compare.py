from flask import Blueprint, abort, render_template

seo_compare_bp = Blueprint("seo_compare", __name__)

COMPARISONS = {
    "paper-timesheets": {
        "label": "Work-A-Beez vs Paper Timesheets",
        "title": "Paper Timesheet Alternative for Small Business | Work-A-Beez",
        "description": "Compare paper timesheets with browser-based employee time tracking. See how Work-A-Beez handles PIN clock-in, authorized devices, schedules and payroll-ready records.",
        "h1": "A Practical Alternative to Paper Timesheets",
        "lede": "Paper can work for a very small team, but every handwritten timecard eventually has to be collected, checked and turned into payroll data. Work-A-Beez moves that workflow into one browser-based system.",
        "old_way": "Employees write or sign their hours on paper, managers collect the sheets, and someone manually totals or re-enters the time before payroll.",
        "workabeez_way": "Employees clock in and out with an ID and PIN from employer-authorized computers. Managers review time entries, schedules, attendance and payroll-ready records online.",
        "differences": [
            ("Clock-in record", "Handwritten or manager-entered", "Recorded digitally at clock-in/out"),
            ("Workplace control", "Depends on process and supervision", "Can require an employer-authorized computer"),
            ("Payroll preparation", "Manual totaling or re-entry", "Hours are already stored for review and reporting"),
            ("Corrections", "Cross-outs, new sheets or manual notes", "Managers can review and correct time entries in the system"),
        ],
        "best_for": "Businesses that are spending manager time collecting, totaling or re-keying paper timecards and want a controlled workplace clock without buying dedicated punch-clock hardware.",
    },
    "spreadsheet-time-tracking": {
        "label": "Work-A-Beez vs Spreadsheet Time Tracking",
        "title": "Spreadsheet Time Tracking Alternative | Work-A-Beez",
        "description": "Looking for an alternative to spreadsheet employee time tracking? Compare manual spreadsheet workflows with Work-A-Beez browser-based clock-in and payroll reporting.",
        "h1": "An Alternative to Spreadsheet Employee Time Tracking",
        "lede": "Spreadsheets are flexible, but they still depend on people entering, copying and checking time correctly. Work-A-Beez captures clock activity first and lets managers review the records afterward.",
        "old_way": "Managers or employees enter hours into cells, formulas total the week, and copies may be emailed or shared before payroll.",
        "workabeez_way": "Employees create time entries through the clock flow, while managers use the dashboard for schedules, attendance, corrections and payroll reporting.",
        "differences": [
            ("Data entry", "Typed into cells", "Generated from employee clock actions"),
            ("Formula risk", "Depends on spreadsheet formulas and versions", "Time calculations live in the timekeeping workflow"),
            ("Access", "Shared file permissions", "Role-based business application access"),
            ("Clock location control", "Not inherent to a spreadsheet", "Trusted-device controls can limit workplace punches"),
        ],
        "best_for": "Small businesses that have outgrown manually maintained Excel or Google Sheets timecards and want employee clock-in, schedules and payroll records in one workflow.",
    },
    "time-clock-without-gps": {
        "label": "Time Clock Without GPS",
        "title": "Employee Time Clock Without GPS Tracking | Work-A-Beez",
        "description": "Need an employee time clock without GPS tracking? Work-A-Beez can use employer-authorized workplace computers and employee PINs instead of requiring phone GPS for standard clock-in.",
        "h1": "Employee Time Clock Without Requiring GPS Tracking",
        "lede": "Not every workplace needs location tracking on employee phones. For teams that report to an office, store, shop, warehouse or other fixed workplace, an authorized computer can be the clock-in control instead.",
        "old_way": "Mobile time-clock systems may rely on employee phones and location permissions to determine where a punch happened.",
        "workabeez_way": "The standard Work-A-Beez workplace clock uses employer-authorized computers plus employee ID and PIN. That provides a fixed punch point without requiring phone GPS for that workflow.",
        "differences": [
            ("Employee device", "Often an employee smartphone", "Can use a company-controlled computer"),
            ("Location control", "Phone location or geofence", "Employer-authorized clock-in device"),
            ("Employee identification", "App account or mobile login", "Company context, employee ID and PIN"),
            ("Best fit", "Mobile or distributed workforces", "Teams reporting to controlled workplace locations"),
        ],
        "best_for": "Employers with on-site teams that want to control where standard clock-in happens without making employee-phone GPS part of the everyday punch process.",
    },
    "employee-phone-clock-in": {
        "label": "Alternative to Employee Phone Clock-In",
        "title": "Alternative to Employee Phone Clock-In Apps | Work-A-Beez",
        "description": "Compare employee phone clock-in apps with Work-A-Beez. Use a shared employer-authorized workplace computer and PIN clock-in instead of requiring personal phones.",
        "h1": "An Alternative to Requiring Employee Phones for Clock-In",
        "lede": "A personal phone app is convenient for some workforces. But if employees already report to a fixed workplace, you may prefer a company-controlled punch point that does not depend on personal devices.",
        "old_way": "Each employee installs or opens a mobile time-clock app, signs in on a personal device and clocks from the phone.",
        "workabeez_way": "Employees can clock from a shared authorized workplace computer using their employee ID and PIN, with no personal phone required for the standard workplace clock flow.",
        "differences": [
            ("Required employee hardware", "Personal smartphone", "No personal phone required"),
            ("Software at punch point", "Mobile app or mobile web", "Standard browser on an authorized computer"),
            ("Shared clock point", "Usually individual devices", "A workplace computer can serve multiple employees"),
            ("Manager control", "Mobile access policy", "Administrator manages authorized clock-in computers"),
        ],
        "best_for": "Retail, warehouse, office, repair-shop and other on-site teams where employees start and end shifts at a company-controlled location.",
    },
    "punch-clock-hardware": {
        "label": "Work-A-Beez vs Punch Clock Hardware",
        "title": "Alternative to Punch Clock Hardware | Work-A-Beez",
        "description": "Compare dedicated employee punch-clock hardware with a browser-based time clock using computers your business already owns. No dedicated time-clock appliance required.",
        "h1": "A Browser-Based Alternative to Dedicated Punch Clock Hardware",
        "lede": "A physical punch clock can create a clear workplace punch point, but it is another device to buy and maintain. Work-A-Beez can turn an existing company computer into the controlled punch point instead.",
        "old_way": "The business purchases and maintains a dedicated punch-clock terminal, card system, tablet kiosk or biometric appliance.",
        "workabeez_way": "The business authorizes an existing computer, opens the browser-based clock and lets employees identify themselves with an ID and PIN.",
        "differences": [
            ("Hardware purchase", "Dedicated device may be required", "Use an existing supported workplace computer"),
            ("Employee credential", "Card, badge, PIN or biometric depending on system", "Employee ID and PIN"),
            ("Administration", "May depend on terminal software or vendor device", "Web-based admin workflow"),
            ("Expansion", "May require another terminal", "Authorize additional computers according to plan limits"),
        ],
        "best_for": "Small and midsize businesses that want a shared workplace punch point without purchasing a dedicated physical time-clock appliance.",
    },
}


@seo_compare_bp.route("/compare")
def compare_hub():
    return render_template(
        "seo_compare.html",
        page=None,
        comparisons=COMPARISONS,
        canonical="https://www.workabeez.net/compare",
    )


@seo_compare_bp.route("/compare/<slug>")
def compare_page(slug):
    page = COMPARISONS.get(slug)
    if page is None:
        abort(404)
    related = [(key, value["label"]) for key, value in COMPARISONS.items() if key != slug]
    return render_template(
        "seo_compare.html",
        page=page,
        slug=slug,
        comparisons=COMPARISONS,
        related=related,
        canonical=f"https://www.workabeez.net/compare/{slug}",
    )


@seo_compare_bp.route("/sitemap-comparisons.xml")
def comparison_sitemap():
    urls = ["https://www.workabeez.net/compare"]
    urls.extend(f"https://www.workabeez.net/compare/{slug}" for slug in COMPARISONS)
    return render_template("seo_sitemap.xml", urls=urls), 200, {"Content-Type": "application/xml; charset=utf-8"}
