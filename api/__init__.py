from api.admin.account_deletion import api_admin_account_deletion_bp
from api.admin.corrections import api_admin_corrections_bp
from api.admin.pto import api_admin_pto_bp
from api.admin.today import api_admin_today_bp
from api.auth_routes import api_auth_bp
from api.employee.account_deletion import api_employee_account_deletion_bp
from api.employee.announcements import api_employee_announcements_bp
from api.employee.clock import api_employee_clock_bp
from api.employee.notifications import api_employee_notifications_bp
from api.employee.pay_stubs import api_employee_pay_stubs_bp
from api.employee.profile import api_employee_profile_bp
from api.employee.pto import api_employee_pto_bp
from api.employee.schedule import api_employee_schedule_bp
from api.employee.time_history import api_employee_time_history_bp
from api.errors import register_error_handlers
from api.push_tokens import api_push_tokens_bp
from seo_best_fit import seo_best_fit_bp
from seo_compare import seo_compare_bp
from seo_industries import seo_industries_bp
from seo_public import seo_public_bp
from seo_tools import seo_tools_bp

API_BLUEPRINTS = [
    api_auth_bp,
    api_employee_clock_bp,
    api_employee_pay_stubs_bp,
    api_employee_pto_bp,
    api_employee_schedule_bp,
    api_employee_time_history_bp,
    api_employee_profile_bp,
    api_employee_announcements_bp,
    api_employee_notifications_bp,
    api_employee_account_deletion_bp,
    api_admin_today_bp,
    api_admin_pto_bp,
    api_admin_corrections_bp,
    api_admin_account_deletion_bp,
    api_push_tokens_bp,
]


def register_api(app, csrf):
    for bp in API_BLUEPRINTS:
        app.register_blueprint(bp)
        csrf.exempt(bp)
    # Public SEO pages are GET-only and intentionally live outside /api.
    # Register separately so they are not unnecessarily CSRF-exempted with
    # the JSON API blueprints.
    app.register_blueprint(seo_public_bp)
    app.register_blueprint(seo_industries_bp)
    app.register_blueprint(seo_tools_bp)
    app.register_blueprint(seo_compare_bp)
    app.register_blueprint(seo_best_fit_bp)
    register_error_handlers(app)
