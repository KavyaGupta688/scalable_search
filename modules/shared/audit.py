"""Cross-cutting audit event store used by every prototype module."""
from __future__ import annotations
from datetime import UTC, datetime
import hashlib, os, uuid
import json
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from dotenv import load_dotenv

load_dotenv()

EVENTS: list[dict[str, object]] = []

def _engine():
    url = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or "sqlite:///platform_audit.db"
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    if "sqlite" in url:
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True)


ENGINE = _engine()
with ENGINE.begin() as conn:
    conn.execute(text("""CREATE TABLE IF NOT EXISTS audit_events (
        event_id VARCHAR(80) PRIMARY KEY,
        action VARCHAR(80) NOT NULL,
        actor VARCHAR(200) NOT NULL,
        user_role VARCHAR(50) DEFAULT 'analyst',
        entity_type VARCHAR(120) NOT NULL,
        entity_id VARCHAR(200) NOT NULL,
        status VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
        occurred_at VARCHAR(40) NOT NULL,
        query_text VARCHAR(500),
        device_code VARCHAR(64),
        location_code VARCHAR(64),
        client_ip VARCHAR(64),
        correlation_id VARCHAR(80),
        execution_time_ms INTEGER DEFAULT 0,
        metadata_json TEXT NOT NULL
    )"""))
    # Non-destructive upgrade for pre-existing SQLite/PostgreSQL tables
    for col_ddl in [
        "ALTER TABLE audit_events ADD COLUMN user_role VARCHAR(50) DEFAULT 'analyst'",
        "ALTER TABLE audit_events ADD COLUMN status VARCHAR(32) DEFAULT 'SUCCESS'",
        "ALTER TABLE audit_events ADD COLUMN client_ip VARCHAR(64)",
        "ALTER TABLE audit_events ADD COLUMN correlation_id VARCHAR(80)",
        "ALTER TABLE audit_events ADD COLUMN execution_time_ms INTEGER DEFAULT 0",
    ]:
        try:
            conn.execute(text(col_ddl))
        except Exception:
            pass

def obfuscate(value: str | None) -> str | None:
    if not value:
        return None
    salt = os.getenv("AUDIT_OBFUSCATION_SALT", "prototype-salt")
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]

def record(action: str, actor: str, entity_type: str, entity_id: str, *,
           user_role: str = "analyst", status: str = "SUCCESS", query: str | None = None,
           device: str | None = None, location: str | None = None, client_ip: str | None = None,
           correlation_id: str | None = None, execution_time_ms: int = 0,
           metadata: dict[str, object] | None = None) -> dict[str, object]:
    event = {
        "event_id": f"audit-{uuid.uuid4().hex[:12]}",

        "action": action,
        "actor": actor,
        "user_role": user_role,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "status": status,
        "occurred_at": datetime.now(UTC),
        "query": query,
        "device_code": obfuscate(device),
        "location_code": obfuscate(location),
        "client_ip": obfuscate(client_ip) if client_ip else None,
        "correlation_id": correlation_id,
        "execution_time_ms": execution_time_ms,
        "metadata": metadata or {},
    }
    EVENTS.append(event)
    with ENGINE.begin() as conn:
        conn.execute(text("""INSERT INTO audit_events
            (event_id, action, actor, user_role, entity_type, entity_id, status, occurred_at,
             query_text, device_code, location_code, client_ip, correlation_id, execution_time_ms, metadata_json)
            VALUES (:event_id, :action, :actor, :user_role, :entity_type, :entity_id, :status, :occurred_at,
                    :query_text, :device_code, :location_code, :client_ip, :correlation_id, :execution_time_ms, :metadata_json)"""), {
            "event_id": event["event_id"],
            "action": event["action"],
            "actor": event["actor"],
            "user_role": event["user_role"],
            "entity_type": event["entity_type"],
            "entity_id": event["entity_id"],
            "status": event["status"],
            "occurred_at": event["occurred_at"].isoformat(),
            "query_text": event["query"],
            "device_code": event["device_code"],
            "location_code": event["location_code"],
            "client_ip": event["client_ip"],
            "correlation_id": event["correlation_id"],
            "execution_time_ms": event["execution_time_ms"],
            "metadata_json": json.dumps(event["metadata"]),
        })
    return event

def list_persisted(*, action: str | None = None, actor: str | None = None,
                   entity_type: str | None = None, entity_id: str | None = None,
                   status: str | None = None, limit: int | None = None) -> list[dict[str, object]]:
    query_parts = ["SELECT * FROM audit_events WHERE 1=1"]
    params: dict[str, object] = {}
    if action:
        query_parts.append("AND action = :action")
        params["action"] = action
    if actor:
        query_parts.append("AND actor = :actor")
        params["actor"] = actor
    if entity_type:
        query_parts.append("AND entity_type = :entity_type")
        params["entity_type"] = entity_type
    if entity_id:
        query_parts.append("AND entity_id = :entity_id")
        params["entity_id"] = entity_id
    if status:
        query_parts.append("AND status = :status")
        params["status"] = status
    query_parts.append("ORDER BY occurred_at DESC")
    if limit:
        query_parts.append("LIMIT :limit")
        params["limit"] = limit

    sql_str = " ".join(query_parts)
    with ENGINE.connect() as conn:
        rows = conn.execute(text(sql_str), params).mappings().all()

    results = []
    for row in rows:
        r = dict(row)
        results.append({
            "event_id": r.get("event_id"),
            "action": r.get("action"),
            "actor": r.get("actor"),
            "user_role": r.get("user_role", "analyst"),
            "entity_type": r.get("entity_type"),
            "entity_id": r.get("entity_id"),
            "status": r.get("status", "SUCCESS"),
            "occurred_at": datetime.fromisoformat(r["occurred_at"]),
            "query": r.get("query_text"),
            "device_code": r.get("device_code"),
            "location_code": r.get("location_code"),
            "client_ip": r.get("client_ip"),
            "correlation_id": r.get("correlation_id"),
            "execution_time_ms": r.get("execution_time_ms", 0),
            "metadata": json.loads(r.get("metadata_json") or "{}"),
        })
    return results

