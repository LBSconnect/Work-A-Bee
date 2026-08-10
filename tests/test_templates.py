"""Static template checks that don't need a running Flask app or database:
Jinja2 syntax validity, and a couple of regression guards for defects found
during the site-health audit.
"""
import glob

import jinja2
import pytest

TEMPLATE_DIR = "templates"
_ENV = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))
_ALL_TEMPLATES = sorted(
    p.removeprefix(TEMPLATE_DIR + "/") for p in glob.glob(f"{TEMPLATE_DIR}/**/*.html", recursive=True)
)


@pytest.mark.parametrize("template_name", _ALL_TEMPLATES)
def test_template_parses(template_name):
    """Every template must be syntactically valid Jinja2, regardless of
    whether the custom filters/functions it calls are registered here."""
    src = _ENV.loader.get_source(_ENV, template_name)[0]
    _ENV.parse(src)  # raises jinja2.TemplateSyntaxError on failure


def test_system_login_not_linked_from_public_marketing_pages():
    """system_login gates a cross-tenant, platform-wide role and is
    documented (app.py) as reachable only by direct URL, never linked from
    a tenant-facing page. Regression guard for a footer link that
    contradicted that on index.html/pricing.html (found during the
    2026-08 site-health audit)."""
    for name in ("index.html", "pricing.html"):
        src = open(f"{TEMPLATE_DIR}/{name}", encoding="utf-8").read()
        assert "system_login" not in src, f"{name} should not link system_login"


def test_subscription_faq_matches_the_actual_trial_length():
    """index.html, pricing.html, and terms.html all promise every new
    customer an unconditional trial - matching plans.py's DEFAULT_PROMO_DAYS
    (organizations.promo_days defaults to that value on creation, so this is
    what actually happens, not just marketing copy). subscription_faq.html
    used to hedge with "availability depends on current promotional programs
    and business policies", contradicting all of the above. Regression guard
    for that inconsistency - and for the trial length drifting out of sync
    across pages again, the way "90-day" (old) vs "14-day" (current) briefly
    did when the length changed."""
    src = open(f"{TEMPLATE_DIR}/subscription_faq.html", encoding="utf-8").read()
    assert "depends on current promotional programs" not in src
    assert "14-day trial" in src
    assert "90-day" not in src


def test_trial_length_is_consistent_across_every_page_that_mentions_it():
    """The site-wide trial length is 14 days (plans.DEFAULT_PROMO_DAYS) as of
    the 2026-08 change from 90 days. A stray leftover "90-day"/"90 days"/
    "ninety (90)" on any customer-facing page would misstate what the site
    (and Stripe) actually do. int_drp.html is exempted - its "90 days" is an
    unrelated disaster-recovery retention period, not a trial length."""
    offenders = []
    for name in _ALL_TEMPLATES:
        if name == "int_drp.html":
            continue
        src = open(f"{TEMPLATE_DIR}/{name}", encoding="utf-8").read()
        if "90-day" in src or "90 days" in src or "90 Days" in src or "ninety (90)" in src:
            offenders.append(name)
    assert not offenders, f"stale 90-day trial wording found in: {offenders}"


def test_all_post_forms_have_csrf_token():
    import re
    form_re = re.compile(r'<form\b[^>]*method=["\']post["\'][^>]*>', re.IGNORECASE)
    offenders = []
    for name in _ALL_TEMPLATES:
        src = open(f"{TEMPLATE_DIR}/{name}", encoding="utf-8").read()
        for m in form_re.finditer(src):
            end = src.find("</form>", m.end())
            if end == -1:
                end = m.end() + 600
            segment = src[m.end():min(end, m.end() + 600)]
            if "csrf_token" not in segment:
                offenders.append(f"{name}:{src[:m.start()].count(chr(10)) + 1}")
    assert not offenders, f"POST forms missing csrf_token: {offenders}"
