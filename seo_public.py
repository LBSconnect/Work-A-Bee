from flask import Blueprint, abort, render_template

seo_public_bp = Blueprint("seo_public", __name__)

PAGES = {
    "employee-time-clock-without-phones": {
        "title": "Employee Time Clock Without Phones | Work-A-Beez",
        "description": "Use a browser-based employee time clock without requiring workers to install an app on personal phones. Work-A-Beez supports PIN clock-in from employer-authorized computers.",
        "h1": "Employee Time Clock Without Phones",
        "eyebrow": "Browser-Based Time Clock",
        "lede": "Keep time tracking on company-controlled computers instead of asking employees to use personal phones. Work-A-Beez lets staff clock in with a PIN from computers your administrator authorizes.",
        "problem": "Many small businesses do not want payroll timekeeping tied to employees' personal phones, app installs, GPS permissions, or battery life. A workplace computer can be simpler when employees already report to a fixed location.",
        "solution": "Work-A-Beez runs in the browser. An administrator registers trusted computers for clock-in use, and employees identify themselves with their employee ID and PIN. No dedicated time-clock hardware is required.",
        "benefits": ["No employee phone app required for workplace clock-in", "Employer-authorized computer access", "PIN-based employee identification", "Browser-based setup with no dedicated time-clock hardware", "Hours flow into timesheets and payroll reporting"],
        "faq": [
            ("Do employees need to use their personal phones?", "No. The workplace clock-in flow can run from employer-authorized computers in a browser."),
            ("Do I need to buy a physical punch clock?", "No dedicated punch-clock appliance is required. Work-A-Beez uses browser-based clock-in on computers you authorize."),
            ("How are employees identified?", "Employees use their company code, employee ID and PIN in the clock-in flow."),
        ],
    },
    "office-computer-employee-time-clock": {
        "title": "Office Computer Employee Time Clock | Work-A-Beez",
        "description": "Turn an office computer into a secure employee time clock. Work-A-Beez uses employer-authorized devices and employee PINs for browser-based clock-in and clock-out.",
        "h1": "Turn an Office Computer Into Your Employee Time Clock",
        "eyebrow": "Trusted-Device Time Tracking",
        "lede": "Use the computer already sitting at your front desk, shop, office, warehouse, or worksite as the place employees clock in and out.",
        "problem": "Separate time-clock hardware adds cost and another device to maintain. Open clock-in links can also make it easier for workers to punch from places you did not intend.",
        "solution": "Work-A-Beez lets an administrator register approved computers as trusted clock-in devices. If a computer is not authorized, the system blocks clock-in for that company.",
        "benefits": ["Use existing workplace computers", "Block clock-in from unapproved computers", "Employee ID and PIN workflow", "No special hardware purchase", "Centralized attendance and payroll-ready records"],
        "faq": [
            ("Can I use a front-desk PC as the time clock?", "Yes. A business can authorize a workplace computer and use it as the employee clock-in point."),
            ("What happens on an unauthorized computer?", "The clock-in flow checks whether the computer is trusted for that organization and blocks the clock action when it is not."),
            ("Can I authorize more than one computer?", "Work-A-Beez plans support different numbers of authorized clock-in devices; see the pricing page for current plan limits."),
        ],
    },
    "pin-employee-time-clock": {
        "title": "PIN Employee Time Clock | Browser-Based Clock In | Work-A-Beez",
        "description": "Simple PIN employee time clock for small businesses. Employees clock in and out from authorized workplace computers using their employee ID and PIN.",
        "h1": "A Simple PIN Employee Time Clock",
        "eyebrow": "Fast Employee Clock-In",
        "lede": "Give employees a quick clock-in workflow without usernames, phone apps, or expensive biometric hardware at the punch point.",
        "problem": "A time clock only works if employees can use it quickly. Complicated sign-in flows create lines, forgotten credentials, and extra manager intervention.",
        "solution": "Work-A-Beez uses a company context plus employee ID and PIN for the workplace clock flow. The computer itself must also be authorized by the employer before it can record clock actions.",
        "benefits": ["Fast PIN-based clock-in", "Trusted-device restriction", "No biometric hardware required", "Works in a standard browser", "Automatic time-entry records for reporting"],
        "faq": [
            ("Is this a biometric time clock?", "No. The standard Work-A-Beez workplace clock flow uses employee ID and PIN rather than biometric hardware."),
            ("Can an employee use another company's clock?", "Employees are matched within the active organization using company and employee credentials."),
            ("Does the PIN replace the trusted-device check?", "No. The employee credential check and the employer-authorized device check work together in the clock-in flow."),
        ],
    },
    "employee-time-clock-kiosk": {
        "title": "Employee Time Clock Kiosk for Small Business | Work-A-Beez",
        "description": "Create a browser-based employee time clock kiosk on a workplace computer. PIN clock-in, authorized-device controls, attendance records and payroll-ready reporting.",
        "h1": "Employee Time Clock Kiosk Without Dedicated Hardware",
        "eyebrow": "Shared Workplace Clock",
        "lede": "Set up a shared workplace computer as a practical clock-in station for hourly teams while keeping clock activity tied to devices your business controls.",
        "problem": "Traditional kiosk hardware can be expensive for a small business, while phone-based systems may not fit teams that all start and end work at the same location.",
        "solution": "Use a browser on an authorized workplace computer as the shared punch point. Employees enter their identifying information and PIN, clock in or out, and Work-A-Beez records the time entry for managers.",
        "benefits": ["Shared browser-based punch point", "Works on employer-authorized computers", "No dedicated kiosk appliance", "PIN-based employee access", "Attendance and time records in one system"],
        "faq": [
            ("Do I need to buy a tablet kiosk?", "No. A computer with a supported browser can serve as the shared clock-in station once the administrator authorizes it."),
            ("Is this useful for small teams?", "Yes. A shared clock point can be a simple fit for offices, shops, warehouses and other teams that report to a workplace."),
            ("Does Work-A-Beez store the clock records?", "Yes. Clock-in and clock-out activity becomes time-entry data used in attendance, timekeeping and payroll reporting workflows."),
        ],
    },
    "prevent-employees-clocking-in-from-home": {
        "title": "Prevent Employees Clocking In From Home | Work-A-Beez",
        "description": "Reduce off-site clock-ins by limiting workplace punches to computers your business authorizes. Work-A-Beez checks trusted devices before employee clock-in and clock-out.",
        "h1": "Help Prevent Employees Clocking In From Home",
        "eyebrow": "Workplace-Only Clock Controls",
        "lede": "If your policy requires employees to clock in at the workplace, make the clock location part of the control instead of relying only on employee behavior.",
        "problem": "A generic web time clock can be reachable from anywhere. For businesses with on-site hourly teams, that can create disputes about whether a punch happened at the workplace.",
        "solution": "Work-A-Beez checks whether the computer is registered as a trusted clock-in device for the organization. An unapproved computer is blocked from completing the workplace clock action.",
        "benefits": ["Restrict punches to approved computers", "Reduce unintended off-site clock-in access", "Employer controls the trusted-device list", "PIN-based employee verification", "Audit-friendly time-entry records"],
        "faq": [
            ("Does this use GPS?", "This specific control is based on employer-authorized computers. It does not require an employee phone GPS check for the standard workplace clock flow."),
            ("Can an administrator change authorized computers?", "Yes. Authorized clock-in devices are managed by the organization administrator."),
            ("Does this guarantee time theft can never happen?", "No software can guarantee that. The trusted-device requirement is one practical control that reduces the ability to clock in from an unapproved computer."),
        ],
    },
}


@seo_public_bp.route("/solutions/<slug>")
def seo_solution(slug):
    page = PAGES.get(slug)
    if page is None:
        abort(404)
    canonical = f"https://www.workabeez.net/solutions/{slug}"
    related = [(key, value["h1"]) for key, value in PAGES.items() if key != slug]
    return render_template("seo_solution.html", page=page, slug=slug, canonical=canonical, related=related)
