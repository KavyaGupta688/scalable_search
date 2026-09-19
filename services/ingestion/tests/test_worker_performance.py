from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ingestion.schemas.job import JobDescriptor, ProcessResult
from ingestion.worker import processor
from ingestion.worker.consumer import _retry_current_message


class FakeConnector:
    async def open_stream(self, _job):
        yield b"image-bytes"


class FakeResult:
    def scalars(self):
        return self

    def first(self):
        return None


class FakeSession:
    def __init__(self):
        self.added = []

    async def scalar(self, _statement):
        return None

    async def execute(self, _statement):
        return FakeResult()

    async def get(self, _model, _identifier):
        return None

    def add(self, value):
        self.added.append(value)

    def add_all(self, values):
        self.added.extend(values)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_zero_copy_worker_streams_once_without_spool_or_tika(monkeypatch):
    connector_id = uuid4()
    source_asset_id = uuid4()
    completed_at = datetime.now(UTC)
    job = JobDescriptor(
        source_type="S3",
        connector_id=connector_id,
        source_ref="bucket/a.jpg",
        provisional_id="etag",
        size_bytes=11,
        etag="etag",
        bucket="bucket",
        object_key="a.jpg",
    )
    metadata_calls = []
    monkeypatch.setattr(processor, "validate_mime_type", lambda *_: "image/jpeg")

    async def fake_source_metadata(*_args, **_kwargs):
        return SimpleNamespace(
            to_orm_dict=lambda: {
                "metadata_formats": ["metadata_csv"],
                "metadata_source_refs": ["bucket/metadata.csv"],
            }
        )

    monkeypatch.setattr(processor, "resolve_source_metadata", fake_source_metadata)

    async def fake_metadata(*args, **kwargs):
        metadata_calls.append(kwargs)
        return SimpleNamespace(
            id=uuid4(),
            first_successful_ingested_at=completed_at,
            to_orm_dict=lambda: {
                "id": uuid4(),
                "checksum_sha256": "a" * 64,
                "size_bytes": 11,
                "mime_type": "image/jpeg",
                "source_connector_id": connector_id,
                "source_ref": "bucket/a.jpg",
                "entitlement_id": uuid4(),
            },
        )

    monkeypatch.setattr(processor, "run_metadata_pipeline", fake_metadata)
    monkeypatch.setattr(processor, "_uuid7", lambda: source_asset_id)
    from unittest.mock import AsyncMock

    enqueue_event = AsyncMock()
    monkeypatch.setattr(processor, "publish_ai_processing_event", enqueue_event)
    result = await processor.process_job(job, FakeConnector(), FakeSession(), producer=None)

    assert result == ProcessResult.SUCCESS
    assert enqueue_event.call_args.kwargs["session"] is not None
    assert metadata_calls[0]["source_asset_id"] == source_asset_id
    assert "content" not in metadata_calls[0]


class FakeMessage:
    def topic(self):
        return "jobs"

    def partition(self):
        return 3

    def offset(self):
        return 42


class FakeConsumer:
    def __init__(self):
        self.positions = []

    def seek(self, position):
        self.positions.append(position)


@pytest.mark.asyncio
async def test_transient_retry_seeks_to_failed_offset(monkeypatch):
    consumer = FakeConsumer()

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("ingestion.worker.consumer.asyncio.sleep", no_sleep)
    await _retry_current_message(consumer, FakeMessage(), 0)

    assert len(consumer.positions) == 1
    assert consumer.positions[0].topic == "jobs"
    assert consumer.positions[0].partition == 3
    assert consumer.positions[0].offset == 42
