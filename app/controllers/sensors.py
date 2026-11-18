from flask import Blueprint, request

from ..errors import ApiError, get_or_404
from ..extensions import db
from ..models import Device, Sensor
from ..validators import apply_sort, choice_arg, validate
from ..views import no_content, ok, paginated, sensor_view

bp = Blueprint("sensors", __name__)

SENSOR_TYPES = ["temperature", "humidity", "soil_moisture", "light", "co2", "pressure", "other"]
SENSOR_SCHEMA = {
    "name": {"type": "str", "required": True, "max": 80},
    "sensor_type": {"type": "str", "required": True, "choices": SENSOR_TYPES},
    "unit": {"type": "str", "required": True, "max": 20},
    "min_valid": {"type": "float"},
    "max_valid": {"type": "float"},
}


def _check_range(min_valid, max_valid):
    if min_valid is not None and max_valid is not None and min_valid >= max_valid:
        raise ApiError(422, "validation_error", "Validasi input gagal",
                       {"min_valid": "harus lebih kecil dari max_valid"})


@bp.post("/devices/<int:device_id>/sensors")
def create_sensor(device_id):
    device = get_or_404(Device, device_id)
    data = validate(request.get_json(silent=True), SENSOR_SCHEMA)
    _check_range(data.get("min_valid"), data.get("max_valid"))
    sensor = Sensor(device_id=device.id, **data)
    db.session.add(sensor)
    db.session.commit()
    return ok(sensor_view(sensor), 201)


@bp.get("/devices/<int:device_id>/sensors")
def list_sensors(device_id):
    device = get_or_404(Device, device_id)
    query = db.select(Sensor).where(Sensor.device_id == device.id)
    sensor_type = choice_arg("sensor_type", SENSOR_TYPES)
    if sensor_type:
        query = query.where(Sensor.sensor_type == sensor_type)
    query = apply_sort(query, Sensor, ["id", "name", "created_at"], default="id")
    return paginated(query, sensor_view)


@bp.get("/sensors/<int:sensor_id>")
def get_sensor(sensor_id):
    return ok(sensor_view(get_or_404(Sensor, sensor_id)))


@bp.route("/sensors/<int:sensor_id>", methods=["PUT", "PATCH"])
def update_sensor(sensor_id):
    sensor = get_or_404(Sensor, sensor_id)
    data = validate(request.get_json(silent=True), SENSOR_SCHEMA, partial=request.method == "PATCH")
    _check_range(data.get("min_valid", sensor.min_valid), data.get("max_valid", sensor.max_valid))
    for key, value in data.items():
        setattr(sensor, key, value)
    db.session.commit()
    return ok(sensor_view(sensor))


@bp.delete("/sensors/<int:sensor_id>")
def delete_sensor(sensor_id):
    sensor = get_or_404(Sensor, sensor_id)
    db.session.delete(sensor)
    db.session.commit()
    return no_content()
