BADGE_TYPES = {
    "team_player": {"icon": "🤝", "label": "Team Player"},
    "above_and_beyond": {"icon": "⭐", "label": "Above & Beyond"},
    "great_attitude": {"icon": "😊", "label": "Great Attitude"},
    "reliable": {"icon": "🛡️", "label": "Rock Solid Reliable"},
    "customer_hero": {"icon": "🏆", "label": "Customer Hero"},
}

MIN_SHIFTS_FOR_AUTO_BADGES = 4


def automated_badges(attendance_summary):
    """Badges earned automatically from real attendance data (last 8 weeks)."""
    badges = []
    if attendance_summary["total_shifts"] >= MIN_SHIFTS_FOR_AUTO_BADGES:
        if attendance_summary["missed"] == 0:
            badges.append({
                "icon": "🎯",
                "label": "Perfect Attendance",
                "detail": f"{attendance_summary['total_shifts']} scheduled shifts worked, zero missed",
            })
        if attendance_summary["late"] == 0 and attendance_summary["missed"] == 0:
            badges.append({
                "icon": "⏰",
                "label": "Punctuality Pro",
                "detail": f"{attendance_summary['total_shifts']} scheduled shifts, always on time",
            })
    return badges
