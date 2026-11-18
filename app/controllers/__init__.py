from . import alerts, devices, sensors, telemetry, users


def register_blueprints(app):
    for module in (users, devices, sensors, telemetry, alerts):
        app.register_blueprint(module.bp, url_prefix="/api/v1")
