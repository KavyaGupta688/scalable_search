"""Persistence regressions run against the isolated integration PostgreSQL instance."""

import os
import uuid
import pytest
from modules.shared.audit import record, list_persisted
from modules.shared.integration import database_engine
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL_SYNC"), reason="Integration PostgreSQL is required"
)


def test_audit_idempotency_filter_and_correlation():
    key = "test-" + uuid.uuid4().hex
    for _ in range(2):
        record(
            "TEST_AUDIT",
            "integration-test",
            "document",
            "canonical",
            event_id=key,
            correlation_id="test-correlation",
            metadata={"value": "preserved"},
        )
    rows = list_persisted(action="TEST_AUDIT", actor="integration-test", limit=500)
    matches = [r for r in rows if r["event_id"] == key]
    assert len(matches) == 1 and matches[0]["correlation_id"] == "test-correlation"
    assert matches[0]["metadata"] == {"value": "preserved"}
    with database_engine("audit").begin() as conn:
        conn.execute(text("DELETE FROM audit_events WHERE event_id=:id"), {"id": key})


def test_outbox_transaction_and_deduplication():
    from sqlalchemy.orm import Session
    from modules.shared.delivery import Delivery, enqueue

    key = "test:" + uuid.uuid4().hex
    with Session(database_engine("ingestion")) as session:
        enqueue(session, key, "audit", {"action": "rolled back"})
        session.rollback()
        assert session.get(Delivery, key) is None
        enqueue(session, key, "audit", {"action": "committed"})
        enqueue(session, key, "audit", {"action": "duplicate"})
        session.commit()
        assert session.get(Delivery, key).payload["action"] == "committed"
        session.delete(session.get(Delivery, key))
        session.commit()
