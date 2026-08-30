"""Cross-cutting audit event store used by every prototype module."""
from __future__ import annotations
from datetime import UTC, datetime
import hashlib, os

EVENTS: list[dict[str, object]] = []

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
    return event
