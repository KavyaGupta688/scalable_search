from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ingestion.config import RetentionSettings
from ingestion.retention.service import reconcile_retention_once


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, row_batches, pending=0):
        self.row_batches = list(row_batches)
        self.pending = pending
        self.added = []
        self.commits = 0
        self.rollbacks = 0
        self.executed = []

    async def execute(self, statement):
        self.executed.append(statement)

    async def scalars(self, _query):
        return Rows(self.row_batches.pop(0))

    async def scalar(self, _query):
        return self.pending

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_due_entitlement_is_marked_expired_without_source_deletion():
    now = datetime(2029, 1, 1, tzinfo=UTC)
    entitlement = SimpleNamespace(id=uuid4(), status="active", expires_at=now - timedelta(seconds=1))
    # Second batch: documents under the expired entitlement (none here).
    session = FakeSession([[entitlement], []])

    result = await reconcile_retention_once(
        session=session,
        retention=RetentionSettings(enabled=True, dry_run=False),
        now=now,
    )

    assert result.expired == 1
    assert entitlement.status == "expired"
    assert session.added == []
    assert session.commits == 1
    assert session.executed == []


@pytest.mark.asyncio
async def test_expiry_queues_search_refresh_in_the_same_transaction():
    now = datetime(2029, 1, 1, tzinfo=UTC)
    entitlement = SimpleNamespace(id=uuid4(), status="active", expires_at=now - timedelta(seconds=1))
    document_id = uuid4()
    session = FakeSession([[entitlement], [document_id]])

    await reconcile_retention_once(
        session=session,
        retention=RetentionSettings(enabled=True, dry_run=False),
        now=now,
    )

    assert len(session.executed) == 1
    params = session.executed[0].compile().params
    assert params["kind"] == "search-refresh"
    assert params["payload"] == {"document_id": str(document_id)}
    assert session.commits == 1


@pytest.mark.asyncio
async def test_dry_run_reports_due_without_changing_status():
    now = datetime(2029, 1, 1, tzinfo=UTC)
    entitlement = SimpleNamespace(id=uuid4(), status="active", expires_at=now)
    session = FakeSession([[entitlement]], pending=1)

    result = await reconcile_retention_once(
        session=session,
        retention=RetentionSettings(enabled=True, dry_run=True),
        now=now,
    )

    assert result.dry_run_due == 1
    assert entitlement.status == "active"
    assert session.added == []
