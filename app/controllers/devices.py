from flask import Blueprint, request
from sqlalchemy import or_

from ..errors import ApiError, get_or_404
from ..extensions import db
from ..models import Device, User
from ..services import generate_api_key, hash_api_key
from ..validators import apply_sort, choice_arg, int_arg, validate
from ..views import device_view, no_content, ok, paginated

bp = Blueprint("devices", __name__)

DEVICE_TYPES = ["esp32", "esp8266", "raspberry_pi", "arduino", "gateway", "other"]
STATUSES = ["active", "inactive", "maintenance"]
DEVICE_SCHEMA = {
    "name": {"type": "str", "required": True, "max": 100},
    "serial_number": {"type": "str", "required": True, "max": 64, "regex": r"^[A-Za-z0-9_-]+$",
                      "regex_msg": "hanya huruf, angka, strip, underscore"},
    "device_type": {"type": "str", "required": True, "choices": DEVICE_TYPES},
    "location": {"type": "str", "max": 120},
    "status": {"type": "str", "choices": STATUSES},
    "owner_id": {"type": "int", "required": True, "ge": 1},
}


def _ensure_owner(owner_id):
    if db.session.get(User, owner_id) is None:
        raise ApiError(422, "validation_error", "Validasi input gagal", {"owner_id": "user tidak ditemukan"})


@bp.post("/devices")
def create_device():
    data = validate(request.get_json(silent=True), DEVICE_SCHEMA)
    _ensure_owner(data["owner_id"])
    api_key = generate_api_key()
    device = Device(**data, api_key_hash=hash_api_key(api_key))
    db.session.add(device)
    db.session.commit()
    body = device_view(device)
    body["api_key"] = api_key  # hanya ditampilkan sekali saat dibuat
    return ok(body, 201)


@bp.get("/devices")
def list_devices():
    query = db.select(Device)
    status = choice_arg("status", STATUSES)
    if status:
        query = query.where(Device.status == status)
    device_type = choice_arg("device_type", DEVICE_TYPES)
    if device_type:
        query = query.where(Device.device_type == device_type)
    owner_id = int_arg("owner_id", None)
    if owner_id:
        query = query.where(Device.owner_id == owner_id)
    q = request.args.get("q", "").strip()
    if q:
        query = query.where(or_(Device.name.ilike(f"%{q}%"), Device.serial_number.ilike(f"%{q}%"),
                                Device.location.ilike(f"%{q}%")))
    query = apply_sort(query, Device, ["id", "name", "created_at", "last_seen_at"], default="id")
    return paginated(query, device_view)


@bp.get("/devices/<int:device_id>")
def get_device(device_id):
    return ok(device_view(get_or_404(Device, device_id)))


@bp.route("/devices/<int:device_id>", methods=["PUT", "PATCH"])
def update_device(device_id):
    device = get_or_404(Device, device_id)
    data = validate(request.get_json(silent=True), DEVICE_SCHEMA, partial=request.method == "PATCH")
    if "owner_id" in data:
        _ensure_owner(data["owner_id"])
    for key, value in data.items():
        setattr(device, key, value)
    db.session.commit()
    return ok(device_view(device))


@bp.post("/devices/<int:device_id>/rotate-key")
def rotate_key(device_id):
    device = get_or_404(Device, device_id)
    api_key = generate_api_key()
    device.api_key_hash = hash_api_key(api_key)
    db.session.commit()
    return ok({"id": device.id, "api_key": api_key})


@bp.delete("/devices/<int:device_id>")
def delete_device(device_id):
    device = get_or_404(Device, device_id)
    db.session.delete(device)
    db.session.commit()
    return no_content()
