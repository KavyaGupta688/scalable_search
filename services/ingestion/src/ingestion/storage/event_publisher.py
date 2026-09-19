"""
Enqueue AI processing events in the document transaction.

A separate outbox worker publishes committed records to Kafka. A rollback
therefore cannot expose unfinished documents to downstream processing.
"""

from __future__ import annotations

from uuid import UUID

from ingestion.config import KafkaSettings
from ingestion.monitoring.logging import get_logger
from ingestion.schemas.metadata import DocumentMetadata
from ingestion.schemas.source_metadata import StructuredSourceMetadata

logger = get_logger(__name__)


async def publish_ai_processing_event(
    producer,
    metadata: DocumentMetadata,
    settings: KafkaSettings,
    structured_metadata: StructuredSourceMetadata | None = None,
    run_id: UUID | None = None,
    session=None,
) -> None:
    """
    Persist an AI event atomically with the newly ingested document.

    The producer argument remains for worker-call compatibility; it is not used.
    """

    event = {
        "run_id": str(run_id) if run_id else None,
        "document_id": str(metadata.id),
        "source_asset_id": str(metadata.source_asset_id),
        "mime_type": metadata.mime_type,
        "checksum_sha256": metadata.checksum_sha256,
        "size_bytes": metadata.size_bytes,
        "source_connector_id": str(metadata.source_connector_id),
        "source_ref": metadata.source_ref,
        "source_type": metadata.source_type,
        "source_etag": metadata.source_etag,
        "source_version_id": metadata.source_version_id,
        "source_last_modified_at": (
            metadata.source_last_modified_at.isoformat() if metadata.source_last_modified_at else None
        ),
        "entitlement_id": str(metadata.entitlement_id),
        "first_successful_ingested_at": metadata.first_successful_ingested_at.isoformat(),
        "effective_expiry_at": metadata.effective_expiry_at.isoformat(),
        "metadata_available": structured_metadata is not None,
        "metadata": structured_metadata.to_event_dict() if structured_metadata else None,
    }

    if session is None:
        raise RuntimeError("AI events require the ingestion transaction")
    from modules.shared.delivery import enqueue_async

    await enqueue_async(session, "ingested:" + str(metadata.id), "ai-processing", event)
