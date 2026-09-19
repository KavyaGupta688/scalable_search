from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ingestion.models.connector import SourceType
from ingestion.schemas.job import JobDescriptor
from ingestion.services.source_access import source_asset_job
from ingestion.storage.event_publisher import publish_ai_processing_event
from ingestion.worker.processor import _same_enumerated_source


def _asset(**overrides):
    values = {
        "id": uuid4(),
        "document_id": uuid4(),
        "source_connector_id": uuid4(),
        "source_type": "S3",
        "source_ref": "bucket/prefix/file.jpg",
        "size_bytes": 12,
        "etag": "etag-1",
        "source_version_id": None,
        "source_last_modified_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_listing_fingerprint_skips_only_unchanged_s3_object():
    asset = _asset()
    unchanged = JobDescriptor(
        source_type="S3",
        connector_id=asset.source_connector_id,
        source_ref=asset.source_ref,
        size_bytes=12,
        etag="etag-1",
        provisional_id="etag-1",
    )
    changed = unchanged.model_copy(update={"etag": "etag-2"})

    assert _same_enumerated_source(asset, unchanged) is True
    assert _same_enumerated_source(asset, changed) is False


def test_smb_source_asset_reconstructs_relative_path():
    connector = SimpleNamespace(
        id=uuid4(),
        source_type=SourceType.NAS_SMB,
        mount_path=r"\\nas-host\media\licensed",
        bucket=None,
    )
    asset = _asset(
        source_connector_id=connector.id,
        source_type="NAS_SMB",
        source_ref="media/licensed/images/a.jpg",
        etag=None,
    )

    job = source_asset_job(asset, connector)

    assert job.relative_path == "images/a.jpg"
    assert job.source_ref == asset.source_ref


class FakeProducer:
    def __init__(self):
        self.message = None

    def produce(self, topic, key, value):
        self.message = (topic, key, json.loads(value))

    def poll(self, _timeout):
        return None


@pytest.mark.asyncio
async def test_ai_event_uses_source_asset_and_never_contains_credentials_or_copy_path():
    producer = FakeProducer()
    metadata = SimpleNamespace(
        id=uuid4(),
        source_asset_id=uuid4(),
        mime_type="image/jpeg",
        checksum_sha256="a" * 64,
        size_bytes=12,
        source_connector_id=uuid4(),
        source_ref="bucket/a.jpg",
        source_type="S3",
        source_etag="etag",
        source_version_id=None,
        source_last_modified_at=datetime(2026, 1, 1, tzinfo=UTC),
        entitlement_id=uuid4(),
        first_successful_ingested_at=datetime(2026, 1, 2, tzinfo=UTC),
        effective_expiry_at=datetime(2029, 1, 2, tzinfo=UTC),
    )
    settings = SimpleNamespace(ai_processing_topic="ai-processing-events")

    run_id = uuid4()
    await publish_ai_processing_event(producer, metadata, settings, run_id=run_id)

    payload = producer.message[2]
    assert payload["source_asset_id"] == str(metadata.source_asset_id)
    assert payload["run_id"] == str(run_id)
    assert "storage_path" not in payload
    assert "access_key" not in payload
    assert "secret_key" not in payload
