from flask import Flask, jsonify

from .cli import register_cli
from .controllers import register_blueprints
from .errors import register_error_handlers
from .extensions import db


def create_app(config_object="config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    register_error_handlers(app)
    register_blueprints(app)
    register_cli(app)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "iot-greenhouse-api", "version": "1.0.0"})

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
