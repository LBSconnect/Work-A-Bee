from datetime import timedelta

import config
from tz import now_in

PROMO_DAYS = 90

PLANS = {
    "starter": {
        "label": "Starter",
        "price": 0,
        "max_employees": 5,
        "max_devices": 1,
        "stripe_price_env": "STRIPE_PRICE_STARTER",
    },
    "growth": {
        "label": "Growth",
        "price": 29,
        "max_employees": 25,
        "max_devices": 3,
        "stripe_price_env": "STRIPE_PRICE_GROWTH",
    },
    "business": {
        "label": "Business",
        "price": 79,
        "max_employees": 100,
        "max_devices": None,
        "stripe_price_env": "STRIPE_PRICE_BUSINESS",
    },
}

DEFAULT_PLAN = "starter"

TIER_RANK = {"starter": 0, "growth": 1, "business": 2}

# Features that are visible on every plan but only usable once the org's plan
# (or an active 90-day promo, which grants full access regardless of plan -
# see the pricing page's "full, unlimited access free for the first 90 days")
# meets the listed minimum tier.
FEATURE_TIERS = {
    "messaging": "growth",
    "notifications": "growth",
    "shift_marketplace": "growth",
    "performance": "business",
    "recognition": "business",
}


def feature_available(org, feature_key):
    if promo_active(org):
        return True
    required = FEATURE_TIERS.get(feature_key)
    if required is None:
        return True
    return TIER_RANK[get_plan_key(org)] >= TIER_RANK[required]


def stripe_price_id(plan_key):
    env_name = PLANS[plan_key]["stripe_price_env"]
    return getattr(config, env_name)


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
