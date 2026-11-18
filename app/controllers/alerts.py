from flask import Blueprint, request

from ..errors import ApiError, get_or_404
from ..extensions import db
from ..models import Alert, AlertRule, Sensor, utcnow
from ..validators import apply_sort, choice_arg, int_arg, validate
from ..views import alert_view, no_content, ok, paginated, rule_view

bp = Blueprint("alerts", __name__)

OPERATOR_CHOICES = ["gt", "gte", "lt", "lte"]
SEVERITIES = ["low", "medium", "high", "critical"]
ALERT_STATUSES = ["open", "acknowledged", "resolved"]
RULE_SCHEMA = {
    "name": {"type": "str", "required": True, "max": 100},
    "operator": {"type": "str", "required": True, "choices": OPERATOR_CHOICES},
    "threshold": {"type": "float", "required": True},
    "severity": {"type": "str", "choices": SEVERITIES},
    "is_active": {"type": "bool"},
}
ALERT_PATCH_SCHEMA = {"status": {"type": "str", "required": True, "choices": ["acknowledged", "resolved"]}}
ALLOWED_TRANSITIONS = {"open": {"acknowledged", "resolved"}, "acknowledged": {"resolved"}, "resolved": set()}


# ---- Alert rules ----
@bp.post("/sensors/<int:sensor_id>/rules")
def create_rule(sensor_id):
    sensor = get_or_404(Sensor, sensor_id)
    data = validate(request.get_json(silent=True), RULE_SCHEMA)
    rule = AlertRule(sensor_id=sensor.id, **data)
    db.session.add(rule)
    db.session.commit()
    return ok(rule_view(rule), 201)


@bp.get("/sensors/<int:sensor_id>/rules")
def list_rules(sensor_id):
    sensor = get_or_404(Sensor, sensor_id)
    query = apply_sort(db.select(AlertRule).where(AlertRule.sensor_id == sensor.id), AlertRule,
                       ["id", "name", "severity", "created_at"], default="id")
    return paginated(query, rule_view)


@bp.route("/rules/<int:rule_id>", methods=["PUT", "PATCH"])
def update_rule(rule_id):
    rule = get_or_404(AlertRule, rule_id, "Rule")
    data = validate(request.get_json(silent=True), RULE_SCHEMA, partial=request.method == "PATCH")
    for key, value in data.items():
        setattr(rule, key, value)
    db.session.commit()
    return ok(rule_view(rule))


@bp.delete("/rules/<int:rule_id>")
def delete_rule(rule_id):
    rule = get_or_404(AlertRule, rule_id, "Rule")
    db.session.delete(rule)
    db.session.commit()
    return no_content()


# ---- Alerts ----
@bp.get("/alerts")
def list_alerts():
    query = db.select(Alert).join(AlertRule, Alert.rule_id == AlertRule.id).join(Sensor, AlertRule.sensor_id == Sensor.id)
    status = choice_arg("status", ALERT_STATUSES)
    if status:
        query = query.where(Alert.status == status)
    severity = choice_arg("severity", SEVERITIES)
    if severity:
        query = query.where(AlertRule.severity == severity)
    device_id = int_arg("device_id", None)
    if device_id:
        query = query.where(Sensor.device_id == device_id)
    query = apply_sort(query, Alert, ["id", "triggered_at", "status"], default="-triggered_at")
    return paginated(query, alert_view)


@bp.get("/alerts/<int:alert_id>")
def get_alert(alert_id):
    return ok(alert_view(get_or_404(Alert, alert_id)))


@bp.patch("/alerts/<int:alert_id>")
def update_alert(alert_id):
    alert = get_or_404(Alert, alert_id)
    data = validate(request.get_json(silent=True), ALERT_PATCH_SCHEMA)
    new_status = data["status"]
    if new_status not in ALLOWED_TRANSITIONS[alert.status]:
        raise ApiError(409, "invalid_transition", f"Status tidak dapat diubah dari '{alert.status}' ke '{new_status}'")
    alert.status = new_status
    if new_status == "resolved":
        alert.resolved_at = utcnow()
    db.session.commit()
    return ok(alert_view(alert))
