from datetime import datetime
from zoneinfo import ZoneInfo

CENTRAL = ZoneInfo("America/Chicago")


def now_central():
    """Current Central time (Texas), correct across CST/CDT, as a naive datetime."""
    return datetime.now(CENTRAL).replace(tzinfo=None)


def today_central():
    return now_central().date()
