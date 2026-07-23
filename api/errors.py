from flask import jsonify
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, code, message, status=400, fields=None, required_plan=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.fields = fields
        self.required_plan = required_plan

    def to_response(self):
        body = {"error": {"code": self.code, "message": self.message, "status": self.status}}
        if self.fields:
            body["error"]["fields"] = self.fields
        if self.required_plan:
            body["error"]["required_plan"] = self.required_plan
        return jsonify(body), self.status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _handle_api_error(err):
        return err.to_response()

    @app.errorhandler(HTTPException)
    def _handle_http_exception(err):
        if not (getattr(err, "code", None) and str(err.code).startswith(("4", "5"))):
            return err
        # Only take over JSON error formatting for API routes; let normal
        # (non-API) HTML error pages behave as they already do.
        from flask import request
        if not request.path.startswith("/api/"):
            return err
        code = {
            404: "not_found",
            405: "method_not_allowed",
            429: "rate_limited",
        }.get(err.code, "http_error")
        return jsonify({"error": {"code": code, "message": err.description, "status": err.code}}), err.code

    @app.errorhandler(Exception)
    def _handle_unexpected_error(err):
        from flask import request
        if not request.path.startswith("/api/"):
            raise err
        return jsonify({"error": {"code": "server_error", "message": "Something went wrong.", "status": 500}}), 500
