"""
Layer 2 - Event Schemas
Standardized data structures for cross-service communication via message brokers.
Ensures consumers receive well-formed, strongly typed JSON payloads.
"""
from typing import List
from datetime import datetime
from pydantic import BaseModel, Field

class EnrichmentRequest(BaseModel):
    """Request enrichment for a file already registered by ingestion."""
    file_id: str

class ProcessingSummary(BaseModel):
    stages_completed: List[str]
    stages_failed: List[str]
    duration_seconds: float
    tags_generated: int
    pii_detected: bool
    nsfw_flagged: bool

class EnrichmentEvent(BaseModel):
    event_type: str
    file_id: str
    metadata_version: str
    model_version: str
    enrichment_version: str
    confidence_aggregate: float
    processing_summary: ProcessingSummary
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class EnrichmentCompletedEvent(EnrichmentEvent):
    event_type: str = "enrichment_completed"

class EnrichmentPartialEvent(EnrichmentEvent):
    event_type: str = "enrichment_partial"
    failed_stages: List[str]

class NeedsReviewEvent(EnrichmentEvent):
    event_type: str = "needs_review"
    review_reasons: List[str]

class EnrichmentFailedEvent(EnrichmentEvent):
    event_type: str = "enrichment_failed"
    error_details: str

if __name__ == "__main__":
    event = EnrichmentCompletedEvent(
        file_id="123",
        metadata_version="1.0",
        model_version="ram_large",
        enrichment_version="1.0.0",
        confidence_aggregate=0.9,
        processing_summary=ProcessingSummary(
            stages_completed=["tagging"],
            stages_failed=[],
            duration_seconds=1.5,
            tags_generated=5,
            pii_detected=False,
            nsfw_flagged=False
        )
    )
    print(event.model_dump_json())
