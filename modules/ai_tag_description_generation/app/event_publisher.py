"""
Layer 3 - Event Publisher
Broadcasts state changes to downstream services (e.g. search indexing, webhooks).
Uses a Redis Stream so events remain available while consumers are offline.
"""
import logging
from modules.ai_tag_description_generation.app.event_schemas import EnrichmentEvent
from modules.ai_tag_description_generation.app.redis_client import event_redis_client

logger = logging.getLogger(__name__)

def publish_enrichment_event(event: EnrichmentEvent) -> None:
    """
    Serializes and publishes a domain event.
    PostgreSQL remains the source of truth; the stream provides durable delivery
    for downstream consumers compared with fire-and-forget Pub/Sub.
    """
    stream = "enrichment_events"
    payload = event.model_dump_json()
    event_id = event_redis_client.xadd(
        stream,
        {"event_type": event.event_type, "document_id": event.document_id, "payload": payload},
        maxlen=100_000,
        approximate=True,
    )
    logger.info("Published %s for document %s to %s as %s", event.event_type, event.document_id, stream, event_id)

if __name__ == "__main__":
    from datetime import datetime
    from modules.ai_tag_description_generation.app.event_schemas import EnrichmentCompletedEvent, ProcessingSummary
    # Simple self-test
    test_event = EnrichmentCompletedEvent(
        document_id="test_001",
        metadata_version="1.0",
        model_version="test",
        enrichment_version="1.0",
        confidence_aggregate=0.99,
        processing_summary=ProcessingSummary(
            stages_completed=["test"],
            stages_failed=[],
            duration_seconds=0.1,
            tags_generated=1,
            pii_detected=False,
            nsfw_flagged=False
        )
    )
    publish_enrichment_event(test_event)
