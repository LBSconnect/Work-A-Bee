from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Chicago"


def now_in(tz_name: str):
    """Current time in tz_name, as a naive datetime (correct across DST)."""
    return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)


def today_in(tz_name: str):
    return now_in(tz_name).date()
