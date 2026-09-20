"""Live RDS smoke checks; writes only normal login/search/Audit events."""
from pathlib import Path
import json
import httpx
from sqlalchemy import text
from modules.shared.integration import database_engine

settings = dict(line.split("=", 1) for line in Path(".integration/stack.env").read_text().splitlines() if "=" in line and not line.startswith("#"))
with database_engine("identity").connect() as conn:
    database = conn.execute(text("SELECT current_database()")).scalar_one()
    assert database == "smsprsm_integration", database
    assert conn.execute(text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")).scalar_one()
print("PASS: RDS integration database and encrypted connection")
with httpx.Client(base_url="http://localhost:8000", timeout=60) as client:
    response = client.post("/auth/login", json={"email":settings["BOOTSTRAP_ADMIN_EMAIL"], "password":settings["BOOTSTRAP_ADMIN_PASSWORD"], "role":"admin"})
    response.raise_for_status()
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    for path in ["/auth/me", "/admin/connectors?limit=10", "/search/facets", "/search/trending", "/datasets/popular", "/downloads?limit=10", "/api/audit/logs?page_size=10"]:
        result = client.get(path)
        print(path, result.status_code)
        result.raise_for_status()
    response = client.post("/search", json={"query":"RDS integration check", "search_mode":"text", "limit":10, "offset":0})
    response.raise_for_status()
    print("PASS: authenticated text search", response.json().get("total"))
    logs = client.get("/api/audit/logs?page_size=50").json()
    assert logs["events"], "Login/search did not produce persisted Audit events"
    print("PASS: Audit events persisted on RDS")
    readiness = client.get("/ready")
    print("Readiness:", readiness.status_code, readiness.text)
