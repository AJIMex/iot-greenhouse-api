"""Lapisan View: serialisasi model ke JSON dan format response yang konsisten."""
from flask import jsonify

from .extensions import db
from .validators import int_arg


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def ok(data, status=200):
    return jsonify({"data": data}), status


def no_content():
    return "", 204


def paginated(query, serializer):
    page = int_arg("page", 1, minimum=1)
    per_page = int_arg("per_page", 10, minimum=1, maximum=100)
    result = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return jsonify({
        "data": [serializer(item) for item in result.items],
        "meta": {"page": page, "per_page": per_page, "total": result.total, "pages": result.pages},
    }), 200


def user_view(u):
    return {"id": u.id, "username": u.username, "email": u.email, "role": u.role,
            "created_at": iso(u.created_at)}


def device_view(d):
    return {"id": d.id, "owner_id": d.owner_id, "name": d.name, "serial_number": d.serial_number,
            "device_type": d.device_type, "location": d.location, "status": d.status,
            "last_seen_at": iso(d.last_seen_at), "created_at": iso(d.created_at)}


def sensor_view(s):
    return {"id": s.id, "device_id": s.device_id, "name": s.name, "sensor_type": s.sensor_type,
            "unit": s.unit, "min_valid": s.min_valid, "max_valid": s.max_valid,
            "created_at": iso(s.created_at)}


def telemetry_view(t):
    return {"id": t.id, "sensor_id": t.sensor_id, "value": t.value, "recorded_at": iso(t.recorded_at)}


def rule_view(r):
    return {"id": r.id, "sensor_id": r.sensor_id, "name": r.name, "operator": r.operator,
            "threshold": r.threshold, "severity": r.severity, "is_active": r.is_active,
            "created_at": iso(r.created_at)}


def alert_view(a):
    return {"id": a.id, "rule_id": a.rule_id, "sensor_id": a.rule.sensor_id,
            "telemetry_id": a.telemetry_id, "severity": a.rule.severity, "message": a.message,
            "status": a.status, "triggered_at": iso(a.triggered_at), "resolved_at": iso(a.resolved_at)}
