from flask import Blueprint, request
from sqlalchemy import func

from ..errors import ApiError, get_or_404
from ..extensions import db
from ..models import Device, Sensor, Telemetry, utcnow
from ..services import api_key_matches, evaluate_rules
from ..validators import apply_sort, datetime_arg, validate
from ..views import ok, paginated, telemetry_view

bp = Blueprint("telemetry", __name__)

MAX_BATCH = 100
READING_SCHEMA = {
    "sensor_id": {"type": "int", "required": True, "ge": 1},
    "value": {"type": "float", "required": True},
    "recorded_at": {"type": "datetime"},
}


def _authenticate_device(device_id):
    """Perangkat harus mengirim header X-API-Key. Pesan error sama untuk device
    tak dikenal maupun key salah agar keberadaan device tidak bocor."""
    api_key = request.headers.get("X-API-Key", "")
    device = db.session.get(Device, device_id)
    if device is None or not api_key or not api_key_matches(api_key, device.api_key_hash):
        raise ApiError(401, "unauthorized", "API key tidak valid")
    if device.status != "active":
        raise ApiError(403, "device_not_active", "Device tidak berstatus active")
    return device


@bp.post("/devices/<int:device_id>/telemetry")
def ingest_telemetry(device_id):
    device = _authenticate_device(device_id)
    payload = request.get_json(silent=True)
    readings = payload.get("readings") if isinstance(payload, dict) and "readings" in payload else [payload]
    if not isinstance(readings, list) or not readings:
        raise ApiError(422, "validation_error", "Validasi input gagal", {"readings": "harus berupa list tidak kosong"})
    if len(readings) > MAX_BATCH:
        raise ApiError(422, "validation_error", "Validasi input gagal", {"readings": f"maksimal {MAX_BATCH} data per request"})

    # Validasi semua dulu agar penyimpanan bersifat all-or-nothing
    prepared = []
    for index, item in enumerate(readings):
        data = validate(item, READING_SCHEMA)
        sensor = db.session.get(Sensor, data["sensor_id"])
        if sensor is None or sensor.device_id != device.id:
            raise ApiError(422, "validation_error", "Validasi input gagal",
                           {f"readings[{index}].sensor_id": "sensor tidak ditemukan pada device ini"})
        if sensor.min_valid is not None and data["value"] < sensor.min_valid or \
                sensor.max_valid is not None and data["value"] > sensor.max_valid:
            raise ApiError(422, "validation_error", "Validasi input gagal",
                           {f"readings[{index}].value": f"di luar rentang valid sensor ({sensor.min_valid} s/d {sensor.max_valid})"})
        prepared.append((sensor, data))

    alerts_triggered = 0
    for sensor, data in prepared:
        reading = Telemetry(sensor=sensor, value=data["value"], recorded_at=data.get("recorded_at") or utcnow())
        db.session.add(reading)
        alerts_triggered += len(evaluate_rules(sensor, reading))
    device.last_seen_at = utcnow()
    db.session.commit()
    return ok({"accepted": len(prepared), "alerts_triggered": alerts_triggered}, 201)


def _filtered(sensor_id):
    query = db.select(Telemetry).where(Telemetry.sensor_id == sensor_id)
    date_from, date_to = datetime_arg("from"), datetime_arg("to")
    if date_from:
        query = query.where(Telemetry.recorded_at >= date_from)
    if date_to:
        query = query.where(Telemetry.recorded_at <= date_to)
    return query


@bp.get("/sensors/<int:sensor_id>/telemetry")
def list_telemetry(sensor_id):
    sensor = get_or_404(Sensor, sensor_id)
    query = apply_sort(_filtered(sensor.id), Telemetry, ["id", "recorded_at", "value"], default="-recorded_at")
    return paginated(query, telemetry_view)


@bp.get("/sensors/<int:sensor_id>/telemetry/stats")
def telemetry_stats(sensor_id):
    sensor = get_or_404(Sensor, sensor_id)
    sub = _filtered(sensor.id).subquery()
    row = db.session.execute(
        db.select(func.count(sub.c.id), func.min(sub.c.value), func.max(sub.c.value), func.avg(sub.c.value))
    ).one()
    count, vmin, vmax, vavg = row
    return ok({"sensor_id": sensor.id, "unit": sensor.unit, "count": count, "min": vmin, "max": vmax,
               "avg": round(vavg, 3) if vavg is not None else None})
