from datetime import timedelta

import config
from tz import now_in

# Trial length granted to brand-new signups going forward - this is what
# billing.create_checkout_session tells Stripe (trial_period_days) when
# creating a new subscription, and what a fresh org's promo_days column
# defaults to (see models.py). It is NOT what promo_active()/promo_days_left()
# below read for an existing org - those read that org's own promo_days
# column, which is fixed at whatever length Stripe actually promised that
# org's card at signup. Changing this constant only changes the length for
# NEW signups; existing orgs keep the length they were already promised
# (see models.py's migration comment for why - Stripe's trial_period_days is
# set once, at subscription-creation time, and never revisited).
DEFAULT_PROMO_DAYS = 14

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
# (or an active trial promo, which grants full access regardless of plan -
# see the pricing page's "full, unlimited access free for the first 14 days")
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


def _promo_days(org):
    """The trial length this specific org was actually promised - its own
    promo_days column, not DEFAULT_PROMO_DAYS (see that constant's comment)."""
    days = org.get("promo_days")
    return days if days is not None else DEFAULT_PROMO_DAYS


def promo_active(org):
    started = org.get("promo_started_at")
    if not started:
        return False
    now = now_in(org.get("timezone") or "America/Chicago")
    return now - started < timedelta(days=_promo_days(org))


def promo_days_left(org):
    started = org.get("promo_started_at")
    if not started:
        return 0
    now = now_in(org.get("timezone") or "America/Chicago")
    left = _promo_days(org) - (now - started).days
    return max(left, 0)


def trial_locked(org):
    """True once a Starter-plan org's trial promo has ended (or was denied
    to begin with - see signup_provision.py) without upgrading. Growth/
    Business orgs are never locked this way - their own plan already has
    real, paid access regardless of the promo."""
    return get_plan_key(org) == "starter" and not promo_active(org)


def employee_limit(org):
    if promo_active(org):
        return None
    return get_plan(org)["max_employees"]


def device_limit(org):
    if promo_active(org):
        return None
    return get_plan(org)["max_devices"]
