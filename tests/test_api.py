from conftest import send


# ---------- Health ----------
def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


# ---------- Users ----------
def test_create_user_success_hides_password(client):
    res = client.post("/api/v1/users", json={
        "username": "andi", "email": "Andi@Example.com", "password": "Rahasia123"})
    assert res.status_code == 201
    data = res.get_json()["data"]
    assert data["email"] == "andi@example.com"
    assert data["role"] == "viewer"
    assert "password" not in data and "password_hash" not in data


def test_create_user_validation_error(client):
    res = client.post("/api/v1/users", json={"username": "a", "email": "bukan-email", "password": "123"})
    assert res.status_code == 422
    body = res.get_json()["error"]
    assert body["code"] == "validation_error"
    assert {"username", "email", "password"} <= set(body["details"])


def test_create_user_duplicate_returns_409(client):
    payload = {"username": "andi", "email": "andi@example.com", "password": "Rahasia123"}
    assert client.post("/api/v1/users", json=payload).status_code == 201
    res = client.post("/api/v1/users", json=payload)
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "conflict"


def test_invalid_json_body_returns_400(client):
    res = client.post("/api/v1/users", data="bukan json", content_type="application/json")
    assert res.status_code == 400


def test_delete_user_with_devices_is_blocked(client, setup):
    res = client.delete(f"/api/v1/users/{setup['user']['id']}")
    assert res.status_code == 409


# ---------- Devices ----------
def test_create_device_returns_api_key_once(client, setup):
    assert setup["key"].startswith("ghk_")
    res = client.get(f"/api/v1/devices/{setup['device']['id']}")
    assert res.status_code == 200
    assert "api_key" not in res.get_json()["data"]


def test_device_not_found_uses_error_format(client):
    res = client.get("/api/v1/devices/9999")
    assert res.status_code == 404
    assert res.get_json()["error"]["code"] == "not_found"


def test_device_list_filter_search_sort_pagination(client, setup):
    for i in range(2, 5):
        client.post("/api/v1/devices", json={
            "name": f"Node {i}", "serial_number": f"GH-TEST-00{i}", "device_type": "esp8266",
            "owner_id": setup["user"]["id"]})
    res = client.get("/api/v1/devices?device_type=esp8266&sort=-name&per_page=2&page=1")
    body = res.get_json()
    assert res.status_code == 200
    assert body["meta"]["total"] == 3 and len(body["data"]) == 2
    assert body["data"][0]["name"] == "Node 4"
    res = client.get("/api/v1/devices?q=GH-TEST-001")
    assert res.get_json()["meta"]["total"] == 1


def test_invalid_sort_field_returns_422(client):
    assert client.get("/api/v1/devices?sort=password_hash").status_code == 422


def test_create_device_with_unknown_owner_returns_422(client):
    res = client.post("/api/v1/devices", json={
        "name": "X", "serial_number": "X-1", "device_type": "esp32", "owner_id": 999})
    assert res.status_code == 422


# ---------- Telemetry & alerts ----------
def test_ingest_success_without_alert(client, setup):
    res = send(client, setup, 25.5)
    assert res.status_code == 201
    assert res.get_json()["data"] == {"accepted": 1, "alerts_triggered": 0}
    stats = client.get(f"/api/v1/sensors/{setup['sensor']['id']}/telemetry/stats").get_json()["data"]
    assert stats["count"] == 1 and stats["avg"] == 25.5


def test_ingest_requires_valid_api_key(client, setup):
    assert send(client, setup, 25, key="salah").status_code == 401
    res = client.post(f"/api/v1/devices/{setup['device']['id']}/telemetry",
                      json={"sensor_id": setup["sensor"]["id"], "value": 25})
    assert res.status_code == 401


def test_ingest_value_out_of_physical_range_rejected(client, setup):
    res = send(client, setup, 500)
    assert res.status_code == 422
    assert "readings[0].value" in res.get_json()["error"]["details"]


def test_ingest_sensor_of_other_device_rejected(client, setup):
    other = client.post("/api/v1/devices", json={
        "name": "Other", "serial_number": "GH-OTHER", "device_type": "esp32",
        "owner_id": setup["user"]["id"]}).get_json()["data"]
    s = client.post(f"/api/v1/devices/{other['id']}/sensors", json={
        "name": "t", "sensor_type": "temperature", "unit": "C"}).get_json()["data"]
    res = client.post(f"/api/v1/devices/{setup['device']['id']}/telemetry",
                      json={"sensor_id": s["id"], "value": 20}, headers={"X-API-Key": setup["key"]})
    assert res.status_code == 422


def test_batch_ingest(client, setup):
    sid = setup["sensor"]["id"]
    res = client.post(f"/api/v1/devices/{setup['device']['id']}/telemetry",
                      json={"readings": [{"sensor_id": sid, "value": 20}, {"sensor_id": sid, "value": 21}]},
                      headers={"X-API-Key": setup["key"]})
    assert res.status_code == 201
    assert res.get_json()["data"]["accepted"] == 2


def test_alert_triggered_and_deduplicated(client, setup):
    assert send(client, setup, 35.0).get_json()["data"]["alerts_triggered"] == 1
    assert send(client, setup, 36.0).get_json()["data"]["alerts_triggered"] == 0  # masih open
    alerts = client.get("/api/v1/alerts?status=open&severity=high").get_json()
    assert alerts["meta"]["total"] == 1
    assert alerts["data"][0]["sensor_id"] == setup["sensor"]["id"]


def test_alert_status_transitions(client, setup):
    send(client, setup, 40)
    alert_id = client.get("/api/v1/alerts").get_json()["data"][0]["id"]
    res = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "acknowledged"})
    assert res.status_code == 200 and res.get_json()["data"]["status"] == "acknowledged"
    res = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "resolved"})
    assert res.get_json()["data"]["resolved_at"] is not None
    res = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "acknowledged"})
    assert res.status_code == 409
    assert res.get_json()["error"]["code"] == "invalid_transition"


def test_inactive_device_cannot_send_telemetry(client, setup):
    client.patch(f"/api/v1/devices/{setup['device']['id']}", json={"status": "maintenance"})
    assert send(client, setup, 25).status_code == 403


def test_delete_sensor_cascades(client, setup):
    send(client, setup, 40)
    assert client.delete(f"/api/v1/sensors/{setup['sensor']['id']}").status_code == 204
    assert client.get("/api/v1/alerts").get_json()["meta"]["total"] == 0
