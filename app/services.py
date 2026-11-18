"""Logika bisnis: keamanan API key perangkat dan evaluasi aturan alert."""
import hashlib
import hmac
import operator
import secrets

from .extensions import db
from .models import Alert

OPERATORS = {"gt": operator.gt, "gte": operator.ge, "lt": operator.lt, "lte": operator.le}
SYMBOLS = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}


def generate_api_key():
    return "ghk_" + secrets.token_urlsafe(32)


def hash_api_key(api_key):
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def api_key_matches(api_key, stored_hash):
    return hmac.compare_digest(hash_api_key(api_key), stored_hash)


def evaluate_rules(sensor, reading):
    """Buat alert baru bila pembacaan melanggar aturan aktif. Tidak membuat duplikat
    selama alert untuk aturan yang sama masih open/acknowledged."""
    created = []
    for rule in sensor.rules:
        if not rule.is_active or not OPERATORS[rule.operator](reading.value, rule.threshold):
            continue
        existing = db.session.scalar(
            db.select(Alert.id)
            .where(Alert.rule_id == rule.id, Alert.status.in_(["open", "acknowledged"]))
            .limit(1)
        )
        if existing:
            continue
        message = (f"{sensor.name}: nilai {reading.value} {sensor.unit} "
                   f"{SYMBOLS[rule.operator]} {rule.threshold} ({rule.name})")
        alert = Alert(rule=rule, telemetry=reading, message=message[:255], status="open")
        db.session.add(alert)
        created.append(alert)
    return created
