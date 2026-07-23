from flask import Blueprint, g, jsonify

from api.auth import api_employee_required
from models import get_db
from tz import now_in

api_employee_schedule_bp = Blueprint("api_employee_schedule", __name__, url_prefix="/api/v1/employee")


@api_employee_schedule_bp.route("/schedule", methods=["GET"])
@api_employee_required
def my_schedule():
    emp = g.api_employee
    org = g.api_org

    with get_db() as conn:
        upcoming_shifts = conn.execute(
            "SELECT * FROM shifts WHERE employee_id=%s AND shift_end >= %s ORDER BY shift_start LIMIT 25",
            (emp["id"], now_in(org["timezone"])),
        ).fetchall()

        offered_shift_ids = {
            row["shift_id"] for row in conn.execute(
                "SELECT shift_id FROM shift_swap_requests WHERE requested_by_employee_id=%s AND status='open'",
                (emp["id"],),
            ).fetchall()
        }

    shifts = [
        {
            "id": s["id"],
            "shift_start": s["shift_start"].isoformat(),
            "shift_end": s["shift_end"].isoformat(),
            "notes": s["notes"],
            "offered_for_swap": s["id"] in offered_shift_ids,
        }
        for s in upcoming_shifts
    ]

    return jsonify({"shifts": shifts})
