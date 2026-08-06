"""Dependency-free unit tests for pure business logic (no database, no Flask
app context needed). Deliberately scoped to modules that don't touch
get_db() - see the CI workflow for why the rest of the app isn't covered
here (it needs a real Postgres instance).
"""
from datetime import timedelta

import pytest

import orgs
import plans
from tz import now_in, today_in


# --- orgs.py -----------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("  Acme-Co  ", "acme-co"),
    ("ACME123", "acme123"),
    ("", ""),
    (None, ""),
])
def test_normalize_company_code(raw, expected):
    assert orgs.normalize_company_code(raw) == expected


@pytest.mark.parametrize("code, valid", [
    ("acme", True),
    ("acme-co-123", True),
    ("cc001", True),
    ("ab", False),          # too short
    ("a" * 33, False),      # too long
    ("Acme", False),        # must already be lowercase
    ("acme_co", False),     # underscore not allowed
    ("", False),
])
def test_is_valid_company_code(code, valid):
    assert orgs.is_valid_company_code(code) is valid


# --- plans.py ------------------------------------------------------------

def _org(**overrides):
    base = {"plan": "starter", "promo_started_at": None, "timezone": "America/Chicago"}
    base.update(overrides)
    return base


def test_get_plan_key_defaults_to_starter_for_unknown_plan():
    assert plans.get_plan_key(_org(plan="not-a-real-plan")) == "starter"
    assert plans.get_plan_key(_org(plan=None)) == "starter"


def test_get_plan_key_recognizes_all_real_plans():
    for key in ("starter", "growth", "business"):
        assert plans.get_plan_key(_org(plan=key)) == key


def test_promo_active_false_when_never_started():
    assert plans.promo_active(_org(promo_started_at=None)) is False


def test_promo_active_true_within_90_days():
    started = now_in("America/Chicago") - timedelta(days=10)
    assert plans.promo_active(_org(promo_started_at=started)) is True


def test_promo_active_false_after_90_days():
    started = now_in("America/Chicago") - timedelta(days=91)
    assert plans.promo_active(_org(promo_started_at=started)) is False


def test_trial_locked_only_applies_to_starter_plan_past_promo():
    started = now_in("America/Chicago") - timedelta(days=91)
    assert plans.trial_locked(_org(plan="starter", promo_started_at=started)) is True
    # Paid plans are never "trial locked" this way, promo or not.
    assert plans.trial_locked(_org(plan="growth", promo_started_at=started)) is False
    assert plans.trial_locked(_org(plan="business", promo_started_at=started)) is False


def test_feature_available_gated_by_tier_unless_promo_active():
    starter_org = _org(plan="starter", promo_started_at=None)
    growth_org = _org(plan="growth", promo_started_at=None)
    business_org = _org(plan="business", promo_started_at=None)

    assert plans.feature_available(starter_org, "messaging") is False
    assert plans.feature_available(growth_org, "messaging") is True
    assert plans.feature_available(starter_org, "performance") is False
    assert plans.feature_available(business_org, "performance") is True

    # A feature with no tier requirement is available on every plan.
    assert plans.feature_available(starter_org, "some_untiered_feature") is True


def test_feature_available_during_active_promo_ignores_tier():
    started = now_in("America/Chicago") - timedelta(days=1)
    starter_on_promo = _org(plan="starter", promo_started_at=started)
    assert plans.feature_available(starter_on_promo, "performance") is True


def test_employee_and_device_limits_waived_during_promo():
    started = now_in("America/Chicago") - timedelta(days=1)
    org_on_promo = _org(plan="starter", promo_started_at=started)
    assert plans.employee_limit(org_on_promo) is None
    assert plans.device_limit(org_on_promo) is None


def test_employee_and_device_limits_apply_after_promo_ends():
    started = now_in("America/Chicago") - timedelta(days=91)
    org = _org(plan="starter", promo_started_at=started)
    assert plans.employee_limit(org) == plans.PLANS["starter"]["max_employees"]
    assert plans.device_limit(org) == plans.PLANS["starter"]["max_devices"]


# --- tz.py -----------------------------------------------------------------

def test_now_in_returns_naive_datetime():
    dt = now_in("America/Chicago")
    assert dt.tzinfo is None


def test_today_in_matches_now_in_date():
    assert today_in("America/Chicago") == now_in("America/Chicago").date()
