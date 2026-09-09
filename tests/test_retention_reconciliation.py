from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from botocore.exceptions import ClientError

from ingestion.config import RetentionSettings
from ingestion.retention.service import reconcile_retention_once


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, row_batches, scalar_values=(0, 0)):
        self.row_batches = list(row_batches)
        self.scalar_values = list(scalar_values)
        self.commits = 0
        self.rollbacks = 0
        self.added = []

    async def scalars(self, _query):
        return _Rows(self.row_batches.pop(0))

    async def scalar(self, _query):
        return self.scalar_values.pop(0)

    async def execute(self, _query):
        return None

    def add(self, value):
        self.added.append(value)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class FakeMinio:
    def __init__(self, existence_results, delete_error=None):
        self.existence_results = list(existence_results)
        self.delete_error = delete_error
        self.deleted_keys = []

    async def get_bucket_versioning_status(self):
        return "Unversioned"

    async def object_exists_including_versions(self, _key, versioning_status=None):
        return self.existence_results.pop(0)

    async def object_exists(self, _key, version_id=None):
        return self.existence_results.pop(0)

    async def delete_object_and_all_versions(self, key, versioning_status=None):
        if self.delete_error:
            raise self.delete_error
        self.deleted_keys.append(key)
        return 1


def _document(*, expires_at, status="active"):
    return SimpleNamespace(
        id=uuid4(),
        entitlement_id=uuid4(),
        storage_path="connector/path/file.jpg",
        object_version_id=None,
        retention_status=status,
        last_reconciled_at=None,
        deleted_at=None,
    )


@pytest.mark.asyncio
async def test_due_unversioned_object_is_deleted_and_audited() -> None:
    now = datetime(2028, 1, 1, tzinfo=timezone.utc)
    document = _document(expires_at=now - timedelta(seconds=1))
    session = FakeSession([[document], []])
    minio = FakeMinio([True, False])

    result = await reconcile_retention_once(
        minio=minio,
        session=session,
        retention=RetentionSettings(enabled=True, dry_run=False),
        now=now,
    )

    assert result.deleted == 1
    assert minio.deleted_keys == [document.storage_path]
    assert document.retention_status == "deleted_by_reconciler"
    assert document.deleted_at == now
    assert session.added
    assert session.added[0].outcome == "deleted_by_reconciler"
    assert session.commits == 1


@pytest.mark.asyncio
async def test_dry_run_never_deletes_due_object() -> None:
    now = datetime(2028, 1, 1, tzinfo=timezone.utc)
    document = _document(expires_at=now)
    session = FakeSession([[document], []], scalar_values=(1, 0))
    minio = FakeMinio([])

    result = await reconcile_retention_once(
        minio=minio,
        session=session,
        retention=RetentionSettings(enabled=True, dry_run=True),
        now=now,
    )

    assert result.dry_run_due == 1
    assert minio.deleted_keys == []
    assert document.retention_status == "active"


@pytest.mark.asyncio
async def test_permission_failure_is_audited() -> None:
    now = datetime(2028, 1, 1, tzinfo=timezone.utc)
    document = _document(expires_at=now - timedelta(days=1))
    permission_error = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "delete denied"}},
        "DeleteObject",
    )
    session = FakeSession([[document], []], scalar_values=(1, 0))
    minio = FakeMinio([True], delete_error=permission_error)

    result = await reconcile_retention_once(
        minio=minio,
        session=session,
        retention=RetentionSettings(enabled=True, dry_run=False),
        now=now,
    )

    assert result.blocked == 1
    assert document.retention_status == "deletion_failed"
    assert session.added[0].details["error_code"] == "lock_or_permission_block"
    assert "delete denied" in session.added[0].details["error_detail"]


@pytest.mark.asyncio
async def test_nonexpired_missing_object_keeps_audit_row() -> None:
    now = datetime(2028, 1, 1, tzinfo=timezone.utc)
    document = _document(expires_at=now + timedelta(days=1))
    session = FakeSession([[], [document]], scalar_values=(0, 1))
    minio = FakeMinio([False])

    result = await reconcile_retention_once(
        minio=minio,
        session=session,
        retention=RetentionSettings(enabled=True, dry_run=False),
        now=now,
    )

    assert result.missing_before_expiry == 1
    assert document.retention_status == "missing_before_expiry"
    assert document.deleted_at is None
