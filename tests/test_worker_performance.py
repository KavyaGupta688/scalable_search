from __future__ import annotations

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

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


class FakeMinIO:
    def __init__(self):
        self.puts = []
        self.multipart_created = False

    async def object_exists(self, _key):
        return False

    async def put_object(self, key, data, content_type):
        self.puts.append((key, data, content_type))

    async def create_multipart_upload(self, _key):
        self.multipart_created = True
        return "upload-id"


@pytest.mark.asyncio
async def test_small_object_uses_single_put_and_inline_tika_content(monkeypatch):
    connector_id = uuid4()
    job = JobDescriptor(
        source_type="S3",
        connector_id=connector_id,
        source_ref="bucket/a.jpg",
        provisional_id="etag",
        size_bytes=11,
        bucket="bucket",
        object_key="a.jpg",
    )
    minio = FakeMinIO()
    metadata_calls = []
    monkeypatch.setattr(processor, "validate_mime_type", lambda *_: "image/jpeg")
    async def fake_metadata(*args, **kwargs):
        metadata_calls.append(kwargs)
        return SimpleNamespace(
            to_orm_dict=lambda: {
                "id": uuid4(),
                "checksum_sha256": "a" * 64,
                "size_bytes": 11,
                "mime_type": "image/jpeg",
                "storage_path": f"{connector_id}/bucket/a.jpg",
                "source_connector_id": connector_id,
                "source_ref": "bucket/a.jpg",
                "entitlement_id": uuid4(),
                "bucket_name": "test-bucket",
                "retention_status": "active",
                "tika_metadata": {},
            }
        )

    monkeypatch.setattr(processor, "run_metadata_pipeline", fake_metadata)
    result = await processor.process_job(
        job, FakeConnector(), FakeSession(), minio, producer=None
    )

    assert result == ProcessResult.SUCCESS
    assert minio.multipart_created is False
    assert minio.puts == [
        (f"{connector_id}/bucket/a.jpg", b"image-bytes", "image/jpeg")
    ]
    assert metadata_calls[0]["content"] == b"image-bytes"


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
