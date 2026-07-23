from datetime import timedelta

from tz import now_in

PROMO_DAYS = 90

PLANS = {
    "starter": {
        "label": "Starter",
        "price": 0,
        "max_employees": 5,
        "max_devices": 1,
    },
    "growth": {
        "label": "Growth",
        "price": 29,
        "max_employees": 25,
        "max_devices": 3,
    },
    "business": {
        "label": "Business",
        "price": 79,
        "max_employees": 100,
        "max_devices": None,
    },
}

DEFAULT_PLAN = "starter"


def get_plan_key(org):
    plan = org.get("plan")
    return plan if plan in PLANS else DEFAULT_PLAN


def get_plan(org):
    return PLANS[get_plan_key(org)]


def promo_active(org):
    created_at = org.get("created_at")
    if not created_at:
        return False
    now = now_in(org.get("timezone") or "America/Chicago")
    return now - created_at < timedelta(days=PROMO_DAYS)


def promo_days_left(org):
    created_at = org.get("created_at")
    if not created_at:
        return 0
    now = now_in(org.get("timezone") or "America/Chicago")
    left = PROMO_DAYS - (now - created_at).days
    return max(left, 0)


def employee_limit(org):
    if promo_active(org):
        return None
    return get_plan(org)["max_employees"]


def device_limit(org):
    if promo_active(org):
        return None
    return get_plan(org)["max_devices"]
