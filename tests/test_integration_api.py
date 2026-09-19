"""Gateway contract tests; backend transport is controlled, identity persistence is real."""

import time
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from modules.shared.auth import dependencies
from modules.shared.auth import service
from modules.shared.auth.models import RegisterRequest
from modules.shared.integration import verify_assertion, assertion
from server import app


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "JWT_SECRET", "test-browser-secret-" * 3)
    monkeypatch.setenv("INTERNAL_JWT_SECRET", "test-internal-secret-" * 3)
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    auth = service.AuthService(tmp_path / "users.json", tmp_path / "tokens.db")
    auth.register(
        RegisterRequest(
            email="admin@example.com", password="test-password-123", role="admin"
        )
    )
    auth.register(
        RegisterRequest(
            email="reader@example.com", password="test-password-123", role="user"
        )
    )
    monkeypatch.setattr(dependencies, "_auth_service", auth)
    events = []
    monkeypatch.setattr(
        "modules.shared.audit.record", lambda *a, **k: events.append((a, k))
    )
    with TestClient(app) as client:
        yield client, auth, events


def login(client, role="user"):
    r = client.post(
        "/auth/login",
        json={
            "email": "admin@example.com" if role == "admin" else "reader@example.com",
            "password": "test-password-123",
            "role": role,
        },
    )
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_credentials_roles_revocation_and_registration(browser):
    c, auth, events = browser
    assert (
        c.post(
            "/auth/login",
            json={
                "email": "admin@example.com",
                "password": "wrong-password",
                "role": "admin",
            },
        ).status_code
        == 401
    )
    assert (
        c.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "test-password-123",
                "role": "admin",
            },
        ).status_code
        == 403
    )
    h = login(c)
    for path in [
        "/admin/connectors",
        "/ai/tasks",
        "/api/audit/logs",
        "/auth/users",
        "/api/admin/overview",
    ]:
        assert c.get(path, headers=h).status_code == 403
    assert c.get("/auth/me", headers=h).status_code == 200
    assert c.post("/auth/logout", headers=h).status_code == 204
    assert c.get("/auth/me", headers=h).status_code == 401
    assert events


def test_forged_identity_and_expired_internal_assertion(browser):
    c, auth, _ = browser
    assert (
        c.get(
            "/admin/connectors", headers={"X-User-Role": "admin", "X-User-Id": "admin"}
        ).status_code
        == 401
    )
    token = assertion("reader", "user", "search")
    with pytest.raises(Exception):
        verify_assertion(token, "ingestion")
    claims = jwt.get_unverified_claims(token)
    claims["exp"] = int(time.time()) - 10
    token = jwt.encode(claims, "test-internal-secret-" * 3, algorithm="HS256")
    with pytest.raises(Exception):
        verify_assertion(token, "search")
    h = login(c)
    claims = jwt.get_unverified_claims(h["Authorization"][7:])
    claims["exp"] = int(time.time()) - 10
    expired = jwt.encode(claims, service.JWT_SECRET, algorithm="HS256")
    assert (
        c.get("/auth/me", headers={"Authorization": "Bearer " + expired}).status_code
        == 401
    )


@pytest.mark.parametrize(
    "method,path,audience,role",
    [
        ("POST", "/search", "search", "user"),
        ("GET", "/search/facets?q=bird", "search", "user"),
        ("GET", "/search/suggestions?q=bird", "search", "user"),
        ("GET", "/datasets/popular", "search", "user"),
        ("GET", "/files/canonical", "search", "user"),
        ("POST", "/events/search", "search", "user"),
        ("GET", "/downloads", "download", "user"),
        ("POST", "/downloads/batch", "download", "user"),
        ("GET", "/admin/connectors", "ingestion", "admin"),
        ("POST", "/admin/ingestion/trigger/id", "ingestion", "admin"),
        ("GET", "/ai/tasks", "ai", "admin"),
    ],
)
def test_route_paths_status_and_signed_identity(browser, method, path, audience, role):
    c, auth, _ = browser
    h = login(c, role)
    captured = []

    async def backend(request):
        captured.append(request)
        claims = verify_assertion(request.headers["authorization"][7:], audience)
        assert claims["role"] == role
        assert "x-user-id" not in request.headers
        return httpx.Response(
            418, json={"detail": "upstream detail"}, headers={"X-Backend": "preserved"}
        )

    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(backend))
    r = c.request(
        method,
        path,
        headers={**h, "X-User-Id": "forged"},
        json={"query": "bird"} if method == "POST" else None,
    )
    assert r.status_code == 418 and r.json()["detail"] == "upstream detail"
    assert r.headers["x-backend"] == "preserved"
    assert captured[0].url.path == path.split("?")[0] + (
        "/" if path == "/admin/connectors" else ""
    )


def test_redesigned_frontend_routes(browser):
    c, _, _ = browser
    for path in [
        "/",
        "/admin/overview",
        "/admin/search",
        "/admin/ingestion",
        "/user/search",
    ]:
        r = c.get(path)
        assert r.status_code == 200
        assert '<div id="root">' in r.text
    assert c.get("/api/unknown").status_code == 404
