from flask import Blueprint, abort, render_template

seo_industries_bp = Blueprint("seo_industries", __name__)

INDUSTRIES = {
    "construction": {
        "label": "Construction Companies",
        "title": "Employee Time Clock for Construction Companies | Work-A-Beez",
        "description": "Browser-based employee time tracking for construction companies with PIN clock-in, employer-authorized devices, schedules, timesheets and payroll reporting.",
        "h1": "Employee Time Tracking for Construction Companies",
        "lede": "Give crews a simple place to clock in at the office, yard, trailer, or other company-controlled location without requiring every worker to install a personal phone app.",
        "challenge": "Construction teams often start work from a shared location, move between jobs, and need dependable records for hourly payroll. A generic clock link that works from any computer may not fit a company that wants a controlled punch point.",
        "fit": "Work-A-Beez lets administrators authorize workplace computers for clock activity and gives employees a PIN-based clock-in flow. Managers can review time entries, schedules, attendance and payroll-ready reporting from the same platform.",
        "benefits": ["Employer-authorized clock-in computers", "Employee ID and PIN workflow", "Schedule and shift visibility", "Break and time-entry records", "Payroll-ready reporting"],
    },
    "cleaning-companies": {
        "label": "Cleaning & Janitorial Companies",
        "title": "Employee Time Clock for Cleaning Companies | Work-A-Beez",
        "description": "Time tracking for cleaning and janitorial companies with PIN clock-in, authorized workplace devices, scheduling, attendance records and payroll reporting.",
        "h1": "Time Tracking for Cleaning & Janitorial Teams",
        "lede": "Keep hourly time, schedules and attendance organized for cleaning crews without turning personal phones into the required company time clock.",
        "challenge": "Cleaning companies may manage early starts, evening shifts, rotating crews and multiple hourly employees. Paper time sheets and manual payroll calculations can create extra administrative work and disputes over punches.",
        "fit": "Work-A-Beez centralizes clock records, employee schedules, breaks and payroll reporting. Where a company uses a fixed dispatch office or shared workplace, administrators can authorize specific computers as clock-in points.",
        "benefits": ["Fast PIN-based employee clock-in", "Centralized time-entry history", "Scheduling and shift management", "Break tracking", "Payroll summary workflows"],
    },
    "property-management": {
        "label": "Property Management Companies",
        "title": "Employee Time Clock for Property Management Companies | Work-A-Beez",
        "description": "Workforce time tracking for property management teams. Manage employee punches, schedules, attendance and payroll records from employer-authorized computers.",
        "h1": "Employee Time Tracking for Property Management Teams",
        "lede": "Track office, maintenance and support staff in one workforce system while keeping your standard workplace clock tied to computers the company controls.",
        "challenge": "Property management teams can include front-office staff, maintenance employees and rotating schedules. Managing time across spreadsheets or disconnected systems makes payroll review and attendance follow-up harder than it needs to be.",
        "fit": "Work-A-Beez combines time entries, employee records, schedules, announcements and payroll reporting. Trusted-device controls can be used when the business wants clock-in activity limited to approved workplace computers.",
        "benefits": ["Office and maintenance staff in one system", "Authorized workplace clock-in", "Scheduling tools", "Employee announcements and notifications", "Payroll-ready time records"],
    },
    "warehouses-logistics": {
        "label": "Warehouses & Logistics",
        "title": "Warehouse Employee Time Clock | Logistics Time Tracking | Work-A-Beez",
        "description": "Browser-based warehouse employee time clock with shared PIN clock-in, authorized devices, shift schedules, attendance and payroll reporting.",
        "h1": "Warehouse & Logistics Employee Time Clock",
        "lede": "Use a shared workplace computer as a straightforward punch point for warehouse and logistics teams that report to a fixed facility or dispatch location.",
        "challenge": "Shift-based operations need fast clock-in without creating a bottleneck at the start of a shift. Managers also need clean time records they can review before payroll.",
        "fit": "Work-A-Beez supports PIN-based employee identification on authorized computers, records clock-in and clock-out activity, and keeps schedules, breaks, attendance and reporting in one system.",
        "benefits": ["Shared browser-based punch point", "PIN employee identification", "Shift scheduling", "Attendance and break records", "Payroll-ready reporting"],
    },
    "retail": {
        "label": "Retail Stores",
        "title": "Employee Time Clock for Retail Stores | Work-A-Beez",
        "description": "Employee time clock for retail stores using a shared authorized computer, PIN clock-in, scheduling, attendance and payroll reporting.",
        "h1": "Employee Time Tracking for Retail Stores",
        "lede": "Turn an existing back-office or manager computer into a shared employee clock-in point for hourly retail teams.",
        "challenge": "Retail stores need a clock process employees can use quickly before and after shifts. Dedicated punch hardware adds cost, while personal-phone clocking may not match a store's operating policy.",
        "fit": "Work-A-Beez runs in the browser and can use employer-authorized computers as workplace clock points. Employees use their ID and PIN while managers handle schedules, attendance records and payroll reporting online.",
        "benefits": ["Use an existing store computer", "PIN-based clock-in", "Employee scheduling", "Attendance and time-entry records", "No dedicated punch-clock appliance required"],
    },
    "auto-repair": {
        "label": "Auto Repair Shops",
        "title": "Employee Time Clock for Auto Repair Shops | Work-A-Beez",
        "description": "Simple employee time tracking for auto repair shops with PIN clock-in from authorized shop computers, schedules, attendance and payroll reporting.",
        "h1": "Employee Time Tracking for Auto Repair Shops",
        "lede": "Give technicians, service staff and office employees one simple way to record work time from a computer the shop already controls.",
        "challenge": "Repair shops often have a mix of technicians and front-office staff working set or staggered schedules. Manual time sheets can add another reconciliation step before payroll.",
        "fit": "Work-A-Beez provides a browser-based clock, trusted-device controls, employee PINs, schedules, break records and payroll reporting without requiring a dedicated physical punch clock.",
        "benefits": ["Shared shop computer clock-in", "Employee ID and PIN", "Schedule visibility", "Break and attendance tracking", "Payroll-ready hour records"],
    },
}


@seo_industries_bp.route("/industries")
def industries_hub():
    return render_template("seo_industry.html", page=None, industries=INDUSTRIES, canonical="https://www.workabeez.net/industries")


@seo_industries_bp.route("/industries/<slug>")
def industry_page(slug):
    page = INDUSTRIES.get(slug)
    if page is None:
        abort(404)
    canonical = f"https://www.workabeez.net/industries/{slug}"
    related = [(key, value["label"]) for key, value in INDUSTRIES.items() if key != slug]
    return render_template("seo_industry.html", page=page, slug=slug, canonical=canonical, related=related, industries=INDUSTRIES)
