from api.auth_routes import api_auth_bp
from api.employee.clock import api_employee_clock_bp
from api.errors import register_error_handlers

API_BLUEPRINTS = [
    api_auth_bp,
    api_employee_clock_bp,
]


def register_api(app, csrf):
    for bp in API_BLUEPRINTS:
        app.register_blueprint(bp)
        csrf.exempt(bp)
    register_error_handlers(app)
