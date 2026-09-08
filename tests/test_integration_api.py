from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


def token(email: str = "analyst@example.com", role: str = "analyst") -> str:
    response = client.post("/auth/token", json={"email": email, "password": "prototype", "role": role})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_and_token_contract():
    assert client.get("/health").json()["status"] == "ok"
    assert token().count(".") == 1


def test_rbac_rejects_viewer_from_enrichment():
    response = client.post(
        "/ai/enrich",
        headers={"Authorization": f"Bearer {token(role='viewer')}"},
        json={"file_id": "file-001", "filename": "panel-crack.jpg"},
    )
    assert response.status_code == 403


def test_audit_log_is_admin_only():
    response = client.get("/downloads/audit/events", headers={"Authorization": f"Bearer {token(role='viewer')}"})
    assert response.status_code == 403


def test_enrichment_and_search_flow():
    headers = {"Authorization": f"Bearer {token()}"}
    enriched = client.post("/ai/enrich", headers=headers, json={"file_id": "file-001", "filename": "panel-crack.jpg"})
    assert enriched.status_code == 202
    assert "panel" in enriched.json()["tags"]

    search = client.post("/search", headers=headers, json={"query": "product", "mode": "text"})
    assert search.status_code == 200
    assert search.json()["total"] >= 1


def test_upload_and_download_audit_flow():
    headers = {"Authorization": f"Bearer {token()}"}
    upload = client.post(
        "/ingestion/upload",
        headers=headers,
        files={"file": ("notes.txt", b"prototype asset", "text/plain")},
    )
    assert upload.status_code == 202
    assert upload.json()["pipeline"]["indexing"] == "queued"

    download = client.post("/downloads/batch", headers=headers, json={"file_ids": ["file-001"]})
    assert download.status_code == 202
    download_id = download.json()["download_id"]
    admin_headers = {"Authorization": f"Bearer {token(role='admin')}"}
    events = client.get("/downloads/audit/events", headers=admin_headers)
    assert events.status_code == 200
    assert any(event["entity_id"] == download_id for event in events.json()["events"])
