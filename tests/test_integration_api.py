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
    monkeypatch.delenv("GATEWAY_METRICS_PORT", raising=False)
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


@pytest.mark.parametrize('path,function',[
    ('/api/admin/ingestion-summary','ingestion_summary'),
    ('/api/admin/ingestion-runs/3261f4cf-8733-48a9-8031-4705671cf6c3/pipeline','run_pipeline'),
])
def test_ingestion_telemetry_is_admin_only(browser,monkeypatch,path,function):
    client,_,_=browser
    monkeypatch.setattr('modules.shared.ingestion_observability.'+function,lambda *args:{'measured':True})
    assert client.get(path).status_code==401
    assert client.get(path,headers=login(client)).status_code==403
    assert client.get(path,headers=login(client,'admin')).json()=={'measured':True}


def test_session_checked_once_per_request_and_revocation_is_immediate(browser, monkeypatch):
    from unittest.mock import Mock
    client, auth, _ = browser
    headers = login(client)
    decode = Mock(wraps=auth.decode_token)
    monkeypatch.setattr(auth, 'decode_token', decode)
    assert client.get('/auth/me', headers=headers).status_code == 200
    assert decode.call_count == 1
    auth.revoke_token(headers['Authorization'][7:])
    assert client.get('/auth/me', headers=headers).status_code == 401


def test_monitoring_failure_has_no_fabricated_or_private_data(browser):
    client, _, _ = browser
    headers = login(client, 'admin')
    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda request: httpx.Response(503, text='private database details')))
    response = client.get('/api/admin/monitoring', headers=headers)
    assert response.status_code == 503
    assert response.json() == {'detail':'Monitoring data is temporarily unavailable'}


def test_metrics_use_route_templates_not_document_ids(browser, monkeypatch):
    from prometheus_client import generate_latest
    client, _, _ = browser
    headers = login(client, 'admin')
    monkeypatch.setattr('modules.shared.observability.document_index',lambda did: {'indexed':False})
    did='6f74e443-a230-4a0b-a434-11a0cc1eca31'
    assert client.get(f'/api/admin/documents/{did}/index',headers=headers).status_code == 200
    metrics=generate_latest().decode()
    assert 'route="/api/admin/documents/{document_id}/index"' in metrics
    assert did not in metrics


def test_cancelled_proxy_request_is_not_a_backend_500(browser):
    from starlette.requests import ClientDisconnect
    client, _, _ = browser
    headers = login(client)
    def cancelled(request):
        raise ClientDisconnect()
    app.state.client=httpx.AsyncClient(transport=httpx.MockTransport(cancelled))
    assert client.get('/downloads',headers=headers).status_code == 499


@pytest.mark.parametrize("operation", ["decode", "user", "audit"])
def test_slow_database_operations_do_not_block_public_health(browser, monkeypatch, operation):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from modules.shared import audit

    client, auth, _ = browser
    headers = login(client)
    entered, release = Event(), Event()
    target, method = (audit, "record") if operation == "audit" else (
        auth, "decode_token" if operation == "decode" else "get_user"
    )
    original = getattr(target, method)

    def slow(*args, **kwargs):
        entered.set()
        assert release.wait(5), "test did not release the blocked operation"
        return original(*args, **kwargs)

    monkeypatch.setattr(target, method, slow)
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(client.request, "POST" if operation == "audit" else "GET",
                                  "/auth/logout" if operation == "audit" else "/auth/me", headers=headers)
        try:
            assert entered.wait(2)
            health = executor.submit(client.get, "/health")
            assert health.result(timeout=2).status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=5).status_code in (200, 204)


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
        "/api/admin/monitoring",
        "/api/admin/documents/00000000-0000-0000-0000-000000000001/index",
    ]:
        assert c.get(path, headers=h).status_code == 403
    assert c.get("/auth/me", headers=h).status_code == 200
    assert c.post("/auth/logout", headers=h).status_code == 204
    assert c.get("/auth/me", headers=h).status_code == 401
    assert events


@pytest.mark.parametrize("operation", ["decode", "user", "audit"])
@pytest.mark.parametrize("failure", ["connection", "pool"])
def test_database_outage_is_unavailable_not_invalid_credentials(browser, monkeypatch, operation, failure):
    from sqlalchemy.exc import OperationalError, TimeoutError
    from modules.shared import audit

    client, auth, _ = browser
    headers = login(client)
    target, method = (audit, "record") if operation == "audit" else (
        auth, "decode_token" if operation == "decode" else "get_user"
    )

    def unavailable(*args, **kwargs):
        if failure == "connection":
            raise OperationalError("private SQL", {}, Exception("private database address"))
        raise TimeoutError("private database address")

    monkeypatch.setattr(target, method, unavailable)
    response = client.request("POST" if operation == "audit" else "GET",
                              "/auth/logout" if operation == "audit" else "/auth/me", headers=headers)
    assert response.status_code == 503
    assert "Database temporarily unavailable" in response.json()["detail"]
    assert "private" not in response.text
    assert response.headers["x-correlation-id"]
    assert client.get("/health").status_code == 200


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


@pytest.mark.parametrize('compressed', [False, True])
def test_proxy_preserves_only_valid_content_length(browser, compressed):
    import gzip
    client, _, _ = browser
    payload = b'protected source bytes'
    wire = gzip.compress(payload) if compressed else payload

    async def backend(request):
        return httpx.Response(200, content=wire, headers={
            'Content-Length': str(len(wire)), 'Cache-Control': 'no-store',
            **({'Content-Encoding': 'gzip'} if compressed else {}),
        })

    app.state.client = httpx.AsyncClient(transport=httpx.MockTransport(backend))
    response = client.get('/downloads/job/content', headers=login(client))
    assert response.content == payload
    assert response.headers['cache-control'] == 'no-store'
    if compressed:
        assert 'content-encoding' not in response.headers
        assert 'content-length' not in response.headers
    else:
        assert response.headers['content-length'] == str(len(payload))


def test_slow_content_entitlement_check_does_not_block_health(browser, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from modules.shared import catalog
    from fastapi import HTTPException

    client, _, _ = browser
    headers = login(client)
    entered, release = Event(), Event()

    def deny_after_delay(ids):
        entered.set()
        assert release.wait(5)
        raise HTTPException(403, 'Access expired')

    monkeypatch.setattr(catalog, 'require_downloadable', deny_after_delay)
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = executor.submit(client.get, '/documents/00000000-0000-0000-0000-000000000001/content', headers=headers)
        try:
            assert entered.wait(2)
            assert executor.submit(client.get, '/health').result(timeout=2).status_code == 200
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 403
