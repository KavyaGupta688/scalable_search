"""Real HTTP acceptance checks, run inside the isolated gateway container."""

import os, uuid, time, json
from pathlib import Path
import httpx

BASE = os.getenv("INTEGRATION_BASE_URL", "http://gateway:8000")
c = httpx.Client(base_url=BASE, timeout=90)


def check(method, path, expected=200, **kwargs):
    r = c.request(method, path, **kwargs)
    assert r.status_code == expected, (
        f"{method} {path}: HTTP {r.status_code}: {r.text[:500]}"
    )
    return r


admin = check(
    "POST",
    "/auth/login",
    json={
        "email": os.environ["BOOTSTRAP_ADMIN_EMAIL"],
        "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"],
        "role": "admin",
    },
).json()["access_token"]
h = {"Authorization": "Bearer " + admin}
email = "acceptance-" + uuid.uuid4().hex[:8] + "@example.com"
password = "Acceptance-password-123"
check(
    "POST",
    "/auth/register",
    expected=403,
    json={"email": email, "password": password, "role": "admin"},
)
check(
    "POST",
    "/auth/register",
    expected=200,
    json={"email": email, "password": password, "role": "user"},
)
user = check(
    "POST", "/auth/login", json={"email": email, "password": password, "role": "user"}
).json()["access_token"]
u = {"Authorization": "Bearer " + user}
for path in ["/admin/connectors", "/ai/tasks", "/api/audit/logs", "/auth/users"]:
    check("GET", path, expected=403, headers=u)
check(
    "GET",
    "/admin/connectors",
    expected=401,
    headers={"X-User-Role": "admin", "X-User-Id": "admin"},
)
for path in ["/", "/admin/overview", "/admin/ingestion", "/user/search"]:
    assert "root" in check("GET", path).text
check("POST", "/search", headers=u, json={"query": "acceptance", "search_mode": "text"})
check("GET", "/datasets/popular", headers=u)
check("GET", "/search/suggestions?q=accept", headers=u)
connector = check(
    "POST",
    "/admin/connectors",
    expected=201,
    headers=h,
    json={
        "name": "Acceptance NAS " + uuid.uuid4().hex[:6],
        "source_type": "NAS_NFS",
        "nas": {
            "protocol": "NFS",
            "mount_path": "/app/.integration/nas",
            "max_files": 10,
        },
    },
).json()
cid = connector["id"]
check("POST", f"/admin/connectors/{cid}/test", headers=h)
run = check("POST", f"/admin/ingestion/trigger/{cid}", headers=h).json()["run_id"]
for _ in range(90):
    state = check("GET", f"/admin/ingestion/runs/{run}", headers=h).json()
    if state["status"] in ("completed", "completed_with_errors", "failed"):
        break
    time.sleep(1)
assert state["status"] == "completed", state
items = check("GET", f"/admin/ingestion/runs/{run}/items", headers=h).json()
ids = list(dict.fromkeys(i["document_id"] for i in items if i.get("document_id")))
assert len(ids) == 5, (state, items)
for did in ids:
    check("GET", f"/documents/{did}/content", headers=h)
    check("GET", f"/documents/{did}/content", headers=u, expected=403)
check("PATCH", f"/admin/connectors/{cid}/archive", headers=h)
check("POST", f"/admin/ingestion/trigger/{cid}", headers=h, expected=409)
check("DELETE", f"/admin/connectors/{cid}", headers=h, expected=409)
check("GET", f"/documents/{ids[0]}/content", headers=h)
check("POST", "/auth/logout", headers=u, expected=204)
check("GET", "/auth/me", headers=u, expected=401)
print(
    json.dumps(
        {
            "verified": "roles, sessions, routes, NAS ingestion, protected streams, archival",
            "connector_id": cid,
            "run_id": run,
            "document_ids": ids,
        }
    )
)
