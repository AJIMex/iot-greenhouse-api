import pytest

from app import create_app
from app.extensions import db


@pytest.fixture()
def app():
    app = create_app("config.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def setup(client):
    """Buat 1 user, 1 device, 1 sensor suhu, 1 rule (suhu > 32). Mengembalikan id + api_key."""
    user = client.post("/api/v1/users", json={
        "username": "budi", "email": "budi@example.com", "password": "Rahasia123", "role": "admin"
    }).get_json()["data"]
    device = client.post("/api/v1/devices", json={
        "name": "Controller A", "serial_number": "GH-TEST-001", "device_type": "esp32",
        "location": "Greenhouse A", "owner_id": user["id"]
    }).get_json()["data"]
    sensor = client.post(f"/api/v1/devices/{device['id']}/sensors", json={
        "name": "temp-1", "sensor_type": "temperature", "unit": "C", "min_valid": -10, "max_valid": 60
    }).get_json()["data"]
    rule = client.post(f"/api/v1/sensors/{sensor['id']}/rules", json={
        "name": "Suhu tinggi", "operator": "gt", "threshold": 32, "severity": "high"
    }).get_json()["data"]
    return {"user": user, "device": device, "sensor": sensor, "rule": rule, "key": device["api_key"]}


def send(client, setup, value, key=None):
    return client.post(
        f"/api/v1/devices/{setup['device']['id']}/telemetry",
        json={"sensor_id": setup["sensor"]["id"], "value": value},
        headers={"X-API-Key": key if key is not None else setup["key"]},
    )
