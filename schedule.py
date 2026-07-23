from datetime import datetime, timedelta

SERIES_GENERATE_WEEKS_AHEAD = 8


def week_bounds(reference_date):
    """Monday-Sunday bounds of the week containing reference_date."""
    days_since_monday = reference_date.weekday()
    week_start = reference_date - timedelta(days=days_since_monday)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def week_days(week_start):
    return [week_start + timedelta(days=i) for i in range(7)]


def generate_series_occurrences(conn, series, through_date):
    """Backfill any missing weekly occurrences for an active shift series, from its
    anchor date through `through_date`. Idempotent - safe to call on every schedule view.
    """
    existing_dates = {
        row["shift_start"].date()
        for row in conn.execute(
            "SELECT shift_start FROM shifts WHERE series_id=%s", (series["id"],)
        ).fetchall()
    }
    d = series["anchor_date"]
    inserted = 0
    while d <= through_date:
        if d not in existing_dates:
            shift_start = datetime.combine(d, series["start_time"])
            shift_end = datetime.combine(d, series["end_time"])
            conn.execute(
                "INSERT INTO shifts (org_id, employee_id, shift_start, shift_end, notes, "
                "created_by_admin_id, series_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (series["org_id"], series["employee_id"], shift_start, shift_end, series["notes"],
                 series["created_by_admin_id"], series["id"]),
            )
            inserted += 1
        d += timedelta(days=7)
    return inserted
