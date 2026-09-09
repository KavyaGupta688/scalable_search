from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def get_admin_token() -> str:
    res = client.post("/auth/token", json={"email": "admin@example.com", "password": "prototype", "role": "admin"})
    assert res.status_code == 200
    return res.json()["access_token"]

def get_analyst_token() -> str:
    res = client.post("/auth/token", json={"email": "analyst@example.com", "password": "prototype", "role": "analyst"})
    assert res.status_code == 200
    return res.json()["access_token"]

def test_extended_audit_event_creation_and_filtering():
    analyst_token = get_analyst_token()
    admin_token = get_admin_token()

    # Post an extended event
    payload = {
        "action": "document.preview",
        "entity_type": "document",
        "entity_id": "doc-uuid-999",
        "status": "SUCCESS",
        "query": "circuit board",
        "device": "workstation-01",
        "location": "BLR-CAMPUS",
        "client_ip": "192.168.1.100",
        "correlation_id": "corr-uuid-12345",
        "execution_time_ms": 42,
        "metadata": {"zoom_level": 2, "viewport": "1920x1080"}
    }
    create_res = client.post("/downloads/events", json=payload, headers={"Authorization": f"Bearer {analyst_token}"})
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["action"] == "document.preview"
    assert created["entity_id"] == "doc-uuid-999"
    assert created["status"] == "SUCCESS"
    assert created["correlation_id"] == "corr-uuid-12345"
    assert created["execution_time_ms"] == 42
    assert created["client_ip"] is not None  # Salted and hashed

    # Filter by action and status
    list_res = client.get(
        "/downloads/audit/events?action=document.preview&status=SUCCESS",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert list_res.status_code == 200
    events = list_res.json()["events"]
    assert any(e["entity_id"] == "doc-uuid-999" for e in events)

def test_audit_csv_export_extended_headers():
    admin_token = get_admin_token()
    csv_res = client.get("/downloads/audit/export.csv", headers={"Authorization": f"Bearer {admin_token}"})
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("text/csv")
    csv_text = csv_res.text
    header_line = csv_text.splitlines()[0]
    assert "user_role" in header_line
    assert "status" in header_line
    assert "client_ip" in header_line
    assert "correlation_id" in header_line
    assert "execution_time_ms" in header_line
