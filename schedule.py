from datetime import timedelta


def week_bounds(reference_date):
    """Monday-Sunday bounds of the week containing reference_date."""
    days_since_monday = reference_date.weekday()
    week_start = reference_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def week_days(week_start):
    return [week_start + timedelta(days=i) for i in range(7)]
