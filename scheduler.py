from datetime import date


def is_report_day(check_date: date) -> bool:
    return check_date.weekday() == 4  # Friday
