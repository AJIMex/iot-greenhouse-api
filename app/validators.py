import math
import re
from datetime import datetime, timezone

from flask import request

from .errors import ApiError

EMAIL_REGEX = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def parse_datetime(value):
    """Parse ISO-8601; hasil disimpan sebagai UTC naive."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def validate(data, schema, partial=False):
    """Validasi body JSON berdasarkan skema sederhana. Field tak dikenal diabaikan."""
    if not isinstance(data, dict):
        raise ApiError(400, "bad_request", "Body harus berupa JSON object")

    errors, clean = {}, {}
    for field, rule in schema.items():
        if field not in data or data[field] is None:
            if rule.get("required") and not partial:
                errors[field] = "wajib diisi"
            continue

        value, kind = data[field], rule["type"]

        if kind == "str":
            if not isinstance(value, str):
                errors[field] = "harus berupa string"
                continue
            if rule.get("strip", True):
                value = value.strip()
            if len(value) < rule.get("min", 1):
                errors[field] = f"minimal {rule.get('min', 1)} karakter"
                continue
            if len(value) > rule.get("max", 255):
                errors[field] = f"maksimal {rule.get('max', 255)} karakter"
                continue
            if "choices" in rule and value not in rule["choices"]:
                errors[field] = "harus salah satu dari: " + ", ".join(rule["choices"])
                continue
            if "regex" in rule and not re.match(rule["regex"], value):
                errors[field] = rule.get("regex_msg", "format tidak valid")
                continue

        elif kind in ("int", "float"):
            ok_type = int if kind == "int" else (int, float)
            if isinstance(value, bool) or not isinstance(value, ok_type):
                errors[field] = "harus berupa angka" if kind == "float" else "harus berupa integer"
                continue
            if kind == "float":
                value = float(value)
                if not math.isfinite(value):
                    errors[field] = "harus berupa angka yang valid"
                    continue
            if "ge" in rule and value < rule["ge"]:
                errors[field] = f"minimal {rule['ge']}"
                continue
            if "le" in rule and value > rule["le"]:
                errors[field] = f"maksimal {rule['le']}"
                continue

        elif kind == "bool":
            if not isinstance(value, bool):
                errors[field] = "harus berupa boolean"
                continue

        elif kind == "datetime":
            if not isinstance(value, str):
                errors[field] = "harus berupa string ISO-8601"
                continue
            try:
                value = parse_datetime(value)
            except ValueError:
                errors[field] = "format harus ISO-8601, contoh 2026-11-16T10:00:00Z"
                continue

        clean[field] = value

    if errors:
        raise ApiError(422, "validation_error", "Validasi input gagal", errors)
    return clean


def _bad_param(name, msg):
    return ApiError(422, "validation_error", f"Parameter '{name}' tidak valid", {name: msg})


def int_arg(name, default, minimum=1, maximum=None):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise _bad_param(name, "harus berupa integer")
    if value < minimum or (maximum is not None and value > maximum):
        raise _bad_param(name, f"harus antara {minimum} dan {maximum if maximum else 'tak hingga'}")
    return value


def choice_arg(name, choices):
    value = request.args.get(name)
    if value is None or value == "":
        return None
    if value not in choices:
        raise _bad_param(name, "harus salah satu dari: " + ", ".join(choices))
    return value


def datetime_arg(name):
    raw = request.args.get(name)
    if not raw:
        return None
    try:
        return parse_datetime(raw)
    except ValueError:
        raise _bad_param(name, "format harus ISO-8601")


def apply_sort(query, model, allowed, default="-id"):
    raw = request.args.get("sort", default)
    descending = raw.startswith("-")
    field = raw.lstrip("-")
    if field not in allowed:
        raise _bad_param("sort", "field harus salah satu dari: " + ", ".join(allowed))
    column = getattr(model, field)
    return query.order_by(column.desc() if descending else column.asc())
