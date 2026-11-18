from flask import Blueprint, request
from sqlalchemy import func, or_

from ..errors import ApiError, get_or_404
from ..extensions import db
from ..models import Device, User
from ..validators import EMAIL_REGEX, apply_sort, choice_arg, validate
from ..views import no_content, ok, paginated, user_view

bp = Blueprint("users", __name__)

ROLES = ["admin", "operator", "viewer"]
USER_SCHEMA = {
    "username": {"type": "str", "required": True, "min": 3, "max": 50,
                 "regex": r"^[A-Za-z0-9_.-]+$", "regex_msg": "hanya huruf, angka, titik, strip, underscore"},
    "email": {"type": "str", "required": True, "max": 120, "regex": EMAIL_REGEX, "regex_msg": "format email tidak valid"},
    "password": {"type": "str", "required": True, "min": 8, "max": 128, "strip": False},
    "role": {"type": "str", "choices": ROLES},
}
USER_UPDATE_SCHEMA = {**USER_SCHEMA, "password": {**USER_SCHEMA["password"], "required": False}}


@bp.post("/users")
def create_user():
    data = validate(request.get_json(silent=True), USER_SCHEMA)
    password = data.pop("password")
    data["email"] = data["email"].lower()
    user = User(**data)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return ok(user_view(user), 201)


@bp.get("/users")
def list_users():
    query = db.select(User)
    role = choice_arg("role", ROLES)
    if role:
        query = query.where(User.role == role)
    q = request.args.get("q", "").strip()
    if q:
        query = query.where(or_(User.username.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    query = apply_sort(query, User, ["id", "username", "created_at"], default="id")
    return paginated(query, user_view)


@bp.get("/users/<int:user_id>")
def get_user(user_id):
    return ok(user_view(get_or_404(User, user_id)))


@bp.route("/users/<int:user_id>", methods=["PUT", "PATCH"])
def update_user(user_id):
    user = get_or_404(User, user_id)
    data = validate(request.get_json(silent=True), USER_UPDATE_SCHEMA, partial=request.method == "PATCH")
    for key, value in data.items():
        if key == "password":
            user.set_password(value)
        elif key == "email":
            user.email = value.lower()
        else:
            setattr(user, key, value)
    db.session.commit()
    return ok(user_view(user))


@bp.delete("/users/<int:user_id>")
def delete_user(user_id):
    user = get_or_404(User, user_id)
    device_count = db.session.scalar(db.select(func.count(Device.id)).where(Device.owner_id == user.id))
    if device_count:
        raise ApiError(409, "conflict", "User masih memiliki device; pindahkan atau hapus device terlebih dahulu")
    db.session.delete(user)
    db.session.commit()
    return no_content()
