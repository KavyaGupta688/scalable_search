"""Cross-cutting audit event store used by every prototype module."""
from __future__ import annotations
from datetime import UTC, datetime
import hashlib, os
import json
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

EVENTS: list[dict[str, object]] = []

def _engine():
    url = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or "sqlite://"
    url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    if url == "sqlite://":
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, pool_pre_ping=True)

ENGINE = _engine()
with ENGINE.begin() as conn:
    conn.execute(text("""CREATE TABLE IF NOT EXISTS audit_events (
        event_id VARCHAR(80) PRIMARY KEY, action VARCHAR(80) NOT NULL,
        actor VARCHAR(200) NOT NULL, entity_type VARCHAR(120) NOT NULL,
        entity_id VARCHAR(200) NOT NULL, occurred_at VARCHAR(40) NOT NULL,
        query_text VARCHAR(500), device_code VARCHAR(64), location_code VARCHAR(64),
        metadata_json TEXT NOT NULL
    )"""))

def obfuscate(value: str | None) -> str | None:
    if not value:
        return None
    salt = os.getenv("AUDIT_OBFUSCATION_SALT", "prototype-salt")
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16]

def record(action: str, actor: str, entity_type: str, entity_id: str, *, query: str | None = None,
           device: str | None = None, location: str | None = None, metadata: dict[str, object] | None = None) -> dict[str, object]:
    event = {
        "event_id": f"audit-{len(EVENTS) + 1:06d}", "action": action, "actor": actor,
        "entity_type": entity_type, "entity_id": entity_id, "occurred_at": datetime.now(UTC),
        "query": query, "device_code": obfuscate(device), "location_code": obfuscate(location),
        "metadata": metadata or {},
    }
    EVENTS.append(event)
    with ENGINE.begin() as conn:
        conn.execute(text("""INSERT INTO audit_events
            (event_id, action, actor, entity_type, entity_id, occurred_at, query_text, device_code, location_code, metadata_json)
            VALUES (:event_id, :action, :actor, :entity_type, :entity_id, :occurred_at, :query_text, :device_code, :location_code, :metadata_json)"""), {
            **event, "occurred_at": event["occurred_at"].isoformat(), "query_text": event["query"],
            "metadata_json": json.dumps(event["metadata"]),
        })
    return event

def list_persisted() -> list[dict[str, object]]:
    with ENGINE.connect() as conn:
        rows = conn.execute(text("SELECT * FROM audit_events ORDER BY occurred_at DESC")).mappings().all()
    return [{**dict(row), "query": row["query_text"], "metadata": json.loads(row["metadata_json"]),
             "occurred_at": __import__("datetime").datetime.fromisoformat(row["occurred_at"])} for row in rows]
