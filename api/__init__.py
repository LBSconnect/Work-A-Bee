from api.auth_routes import api_auth_bp
from api.employee.announcements import api_employee_announcements_bp
from api.employee.clock import api_employee_clock_bp
from api.employee.notifications import api_employee_notifications_bp
from api.employee.pay_stubs import api_employee_pay_stubs_bp
from api.employee.profile import api_employee_profile_bp
from api.employee.pto import api_employee_pto_bp
from api.employee.schedule import api_employee_schedule_bp
from api.employee.time_history import api_employee_time_history_bp
from api.errors import register_error_handlers

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
]


def register_api(app, csrf):
    for bp in API_BLUEPRINTS:
        app.register_blueprint(bp)
        csrf.exempt(bp)
    register_error_handlers(app)
