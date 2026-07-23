from flask import Blueprint, g, jsonify

from api.auth import api_employee_required
from models import get_db

api_employee_profile_bp = Blueprint("api_employee_profile", __name__, url_prefix="/api/v1/employee")


@api_employee_profile_bp.route("/profile", methods=["GET"])
@api_employee_required
def profile():
    emp = g.api_employee

    department_name = None
    if emp.get("department_id"):
        with get_db() as conn:
            department = conn.execute(
                "SELECT name FROM departments WHERE id=%s", (emp["department_id"],)
            ).fetchone()
        department_name = department["name"] if department else None

    return jsonify({
        "employee": {
            "id": emp["id"],
            "name": emp["name"],
            "employee_code": emp["employee_code"],
            "worker_type": emp["worker_type"],
            "hourly_rate": emp["hourly_rate"],
            "email": emp.get("email"),
            "phone": emp.get("phone"),
            "job_title": emp.get("job_title"),
            "department": department_name,
            "pto_balance_hours": emp.get("pto_balance_hours"),
        }
    })
