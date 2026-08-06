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
