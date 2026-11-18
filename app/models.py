from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utcnow():
    """Waktu UTC (naive) agar konsisten di SQLite maupun MySQL."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="viewer")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    devices = db.relationship("Device", back_populates="owner")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    serial_number = db.Column(db.String(64), unique=True, nullable=False)
    device_type = db.Column(db.String(30), nullable=False)
    location = db.Column(db.String(120))
    status = db.Column(db.String(20), nullable=False, default="active")
    api_key_hash = db.Column(db.String(64), nullable=False)  # SHA-256 dari API key perangkat
    last_seen_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    owner = db.relationship("User", back_populates="devices")
    sensors = db.relationship("Sensor", back_populates="device", cascade="all, delete-orphan")


class Sensor(db.Model):
    __tablename__ = "sensors"
    __table_args__ = (db.UniqueConstraint("device_id", "name", name="uq_sensor_device_name"),)

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("devices.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    sensor_type = db.Column(db.String(30), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    min_valid = db.Column(db.Float)  # batas fisik minimum yang masuk akal
    max_valid = db.Column(db.Float)  # batas fisik maksimum yang masuk akal
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    device = db.relationship("Device", back_populates="sensors")
    readings = db.relationship("Telemetry", back_populates="sensor", cascade="all, delete-orphan")
    rules = db.relationship("AlertRule", back_populates="sensor", cascade="all, delete-orphan")


class Telemetry(db.Model):
    __tablename__ = "telemetry_readings"
    __table_args__ = (db.Index("ix_telemetry_sensor_time", "sensor_id", "recorded_at"),)

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey("sensors.id"), nullable=False)
    value = db.Column(db.Float, nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    sensor = db.relationship("Sensor", back_populates="readings")


class AlertRule(db.Model):
    __tablename__ = "alert_rules"

    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer, db.ForeignKey("sensors.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    operator = db.Column(db.String(5), nullable=False)  # gt, gte, lt, lte
    threshold = db.Column(db.Float, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="medium")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    sensor = db.relationship("Sensor", back_populates="rules")
    alerts = db.relationship("Alert", back_populates="rule", cascade="all, delete-orphan")


class Alert(db.Model):
    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("alert_rules.id"), nullable=False, index=True)
    telemetry_id = db.Column(db.Integer, db.ForeignKey("telemetry_readings.id"), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")  # open, acknowledged, resolved
    triggered_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    resolved_at = db.Column(db.DateTime)

    rule = db.relationship("AlertRule", back_populates="alerts")
    telemetry = db.relationship("Telemetry")
