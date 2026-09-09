"""
Publish AI processing events to Kafka for downstream consumers.

After a document is successfully ingested, an event is published to the
ai-processing-events topic so downstream AI tagging/embedding pipelines
can pick it up.
"""

from __future__ import annotations

import json

from ingestion.config import KafkaSettings
from ingestion.schemas.metadata import DocumentMetadata
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)


async def publish_ai_processing_event(
    producer, metadata: DocumentMetadata, settings: KafkaSettings
) -> None:
    """
    Publish an AI processing event for a newly ingested document.

    Uses confluent-kafka Producer.produce() (not kafka-python's send_and_wait).
    """
    topic = settings.ai_processing_topic

    event = {
        "document_id": str(metadata.id),
        "storage_path": metadata.storage_path,
        "mime_type": metadata.mime_type,
        "checksum_sha256": metadata.checksum_sha256,
        "size_bytes": metadata.size_bytes,
        "source_connector_id": str(metadata.source_connector_id),
        "source_ref": metadata.source_ref,
        "entitlement_id": str(metadata.entitlement_id),
        "first_successful_ingested_at": metadata.first_successful_ingested_at.isoformat(),
        "effective_expiry_at": metadata.effective_expiry_at.isoformat(),
    }

    try:
        producer.produce(
            topic,
            key=str(metadata.id).encode("utf-8"),
            value=json.dumps(event).encode("utf-8"),
        )
        producer.poll(0)  # Trigger delivery callbacks
        logger.info(
            f"Published AI processing event for document {metadata.id}",
            extra={
                "document_id": str(metadata.id),
                "topic": topic,
            },
        )
    except Exception as e:
        logger.error(
            f"Failed to publish AI processing event: {e}",
            extra={"document_id": str(metadata.id)},
        )
        raise
