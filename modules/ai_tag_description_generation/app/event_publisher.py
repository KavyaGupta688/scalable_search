"""
Layer 3 - Event Publisher
Broadcasts state changes to downstream services (e.g. search indexing, webhooks).
Uses Redis Pub/Sub for lightweight decoupling.
"""
import json
import logging
import redis
from app.config import settings
from app.event_schemas import EnrichmentEvent

logger = logging.getLogger(__name__)

# Reusing REDIS_URL for pub/sub. Redis allows distinct databases via URL, assuming it's configured nicely.
redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)

def publish_enrichment_event(event: EnrichmentEvent) -> None:
    """
    Serializes and publishes a domain event.
    Failures in publishing should not crash the main pipeline to maintain reliability.
    """
    channel = "enrichment_events"
    payload = event.model_dump_json()
    
    try:
        redis_client.publish(channel, payload)
        logger.info(f"Published {event.event_type} for file {event.file_id} to {channel}")
        
        # In a full system, you could also send a signal back to celery or update a secondary tracker here.
    except Exception as e:
        logger.error(f"Failed to publish event to Redis: {e}", exc_info=True)
        # We deliberately catch and log rather than raise, because the DB transaction 
        # (which happened prior to this) is the source of truth.

if __name__ == "__main__":
    from datetime import datetime
    from app.event_schemas import EnrichmentCompletedEvent, ProcessingSummary
    # Simple self-test
    test_event = EnrichmentCompletedEvent(
        file_id="test_001",
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
