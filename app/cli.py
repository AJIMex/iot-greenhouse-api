import random
from datetime import timedelta

import click

from .extensions import db
from .models import AlertRule, Device, Sensor, Telemetry, User, utcnow
from .services import evaluate_rules, generate_api_key, hash_api_key


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Membuat semua tabel database."""
        db.create_all()
        click.echo("Database dan tabel berhasil dibuat.")

    @app.cli.command("reset-db")
    def reset_db():
        """Menghapus lalu membuat ulang semua tabel (HATI-HATI: data hilang)."""
        db.drop_all()
        db.create_all()
        click.echo("Database di-reset.")

    @app.cli.command("seed")
    def seed():
        """Mengisi data simulasi (synthetic data) greenhouse."""
        db.create_all()
        if db.session.scalar(db.select(User.id).limit(1)):
            click.echo("Data sudah ada; gunakan 'flask reset-db' lalu 'flask seed' untuk mengulang.")
            return

        rng = random.Random(42)
        admin = User(username="admin", email="admin@example.com", role="admin")
        admin.set_password("Admin12345!")
        operator = User(username="operator1", email="operator1@example.com", role="operator")
        operator.set_password("Operator12345!")
        db.session.add_all([admin, operator])
        db.session.flush()

        plans = [
            ("GH-A Controller", "GH-ESP32-001", "esp32", "Greenhouse A", admin),
            ("GH-B Controller", "GH-RPI-002", "raspberry_pi", "Greenhouse B", operator),
        ]
        sensor_defs = [
            ("temp-1", "temperature", "C", -10, 60, 28.0, 2.0, ("Suhu terlalu tinggi", "gt", 32.0, "high")),
            ("hum-1", "humidity", "%", 0, 100, 65.0, 5.0, ("Kelembapan terlalu rendah", "lt", 40.0, "medium")),
            ("soil-1", "soil_moisture", "%", 0, 100, 55.0, 6.0, None),
        ]
        keys = {}
        now = utcnow()
        for name, serial, dtype, location, owner in plans:
            api_key = generate_api_key()
            device = Device(name=name, serial_number=serial, device_type=dtype, location=location,
                            owner_id=owner.id, api_key_hash=hash_api_key(api_key), last_seen_at=now)
            db.session.add(device)
            db.session.flush()
            keys[serial] = api_key
            for s_name, s_type, unit, vmin, vmax, base, noise, rule in sensor_defs:
                sensor = Sensor(device_id=device.id, name=s_name, sensor_type=s_type, unit=unit,
                                min_valid=vmin, max_valid=vmax)
                db.session.add(sensor)
                db.session.flush()
                if rule:
                    db.session.add(AlertRule(sensor_id=sensor.id, name=rule[0], operator=rule[1],
                                             threshold=rule[2], severity=rule[3]))
                    db.session.flush()
                for hour in range(24):
                    value = round(base + rng.uniform(-noise, noise), 2)
                    if hour == 14 and s_type == "temperature":
                        value = 35.4  # lonjakan suhu agar alert terpicu
                    reading = Telemetry(sensor_id=sensor.id, value=value,
                                        recorded_at=now - timedelta(hours=24 - hour))
                    db.session.add(reading)
                    db.session.flush()
                    db.session.refresh(sensor)
                    evaluate_rules(sensor, reading)
        db.session.commit()
        click.echo("Seed selesai. API key perangkat (simpan, hanya tampil sekali):")
        for serial, key in keys.items():
            click.echo(f"  {serial}: {key}")
        click.echo("User demo: admin / Admin12345!  |  operator1 / Operator12345!")
