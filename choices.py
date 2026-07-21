TIMEZONE_CHOICES = [
    ("America/New_York", "Eastern"),
    ("America/Chicago", "Central"),
    ("America/Denver", "Mountain"),
    ("America/Los_Angeles", "Pacific"),
    ("America/Anchorage", "Alaska"),
    ("Pacific/Honolulu", "Hawaii"),
]

CURRENCY_CHOICES = [
    ("USD", "USD - US Dollar"),
    ("CAD", "CAD - Canadian Dollar"),
    ("GBP", "GBP - British Pound"),
]

BUSINESS_TYPE_CHOICES = ["Corporation", "LLC", "Sole Proprietor", "Government", "Nonprofit"]

INDUSTRY_CHOICES = [
    "Construction", "Retail", "Restaurant & Food Service", "Healthcare", "Manufacturing",
    "Professional Services", "Hospitality", "Transportation & Logistics", "Nonprofit", "Other",
]

COUNTRY_CHOICES = ["United States", "Canada", "United Kingdom"]

WEEK_START_CHOICES = [("monday", "Monday"), ("sunday", "Sunday")]

PAYROLL_FREQUENCY_CHOICES = [
    ("weekly", "Weekly"), ("biweekly", "Biweekly"),
    ("semimonthly", "Semi-Monthly"), ("monthly", "Monthly"),
]

SHIFT_LENGTH_CHOICES = [(480, "8 Hours"), (600, "10 Hours"), (720, "12 Hours")]

OVERTIME_RULE_CHOICES = [
    ("daily_8", "After 8 Hours (daily)"),
    ("weekly_40", "After 40 Hours (weekly)"),
    ("custom", "Custom"),
    ("none", "None"),
]

ROUND_CLOCK_CHOICES = [(0, "None"), (1, "Nearest Minute"), (5, "5 Minutes"), (10, "10 Minutes"), (15, "15 Minutes")]

LUNCH_DURATION_CHOICES = [30, 45, 60]

EMPLOYEE_ROLE_CHOICES = [
    ("employee", "Employee"),
    ("supervisor", "Supervisor"),
    ("administrator", "Administrator"),
]
