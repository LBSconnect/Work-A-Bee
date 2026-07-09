from datetime import date

from config import PAY_PERIOD_ANCHOR


def is_report_day(check_date: date) -> bool:
    days_since_anchor = (check_date - PAY_PERIOD_ANCHOR).days
    return days_since_anchor >= 0 and days_since_anchor % 14 == 0
