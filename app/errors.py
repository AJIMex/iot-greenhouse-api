from flask import jsonify
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from .extensions import db


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def error_response(status, code, message, details=None):
    body = {"error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status


def get_or_404(model, pk, label=None):
    obj = db.session.get(model, pk)
    if obj is None:
        raise ApiError(404, "not_found", f"{label or model.__name__} dengan id {pk} tidak ditemukan")
    return obj


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(e):
        return error_response(e.status, e.code, e.message, e.details)

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(e):
        db.session.rollback()
        return error_response(409, "conflict", "Data duplikat atau melanggar constraint integritas")

    @app.errorhandler(HTTPException)
    def handle_http_error(e):
        code = (e.name or "error").lower().replace(" ", "_")
        return error_response(e.code, code, e.description)

    @app.errorhandler(Exception)
    def handle_unexpected(e):
        app.logger.exception("Unhandled error")
        db.session.rollback()
        return error_response(500, "internal_error", "Terjadi kesalahan pada server")
