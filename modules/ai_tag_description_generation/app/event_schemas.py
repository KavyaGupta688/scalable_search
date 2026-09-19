"""
Layer 2 - Event Schemas
Standardized data structures for cross-service communication via message brokers.
Ensures consumers receive well-formed, strongly typed JSON payloads.
"""
from typing import Any, List
from datetime import datetime, timezone
from uuid import UUID
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

class EnrichmentRequest(BaseModel):
    """Request enrichment for a file already registered by ingestion."""
    document_id: UUID = Field(validation_alias=AliasChoices("document_id", "file_id"))


class IngestionDocumentEvent(BaseModel):
    """Contract emitted by ingestion on the ``ai-processing-events`` topic."""

    model_config = ConfigDict(extra="allow")

    run_id: UUID
    document_id: UUID
    source_asset_id: UUID
    mime_type: str
    size_bytes: int = Field(ge=0)
    checksum_sha256: str = Field(min_length=64, max_length=64)
    source_connector_id: UUID
    source_ref: str
    source_type: str
    source_etag: str | None = None
    source_version_id: str | None = None
    source_last_modified_at: datetime | None = None
    entitlement_id: UUID
    first_successful_ingested_at: datetime
    effective_expiry_at: datetime
    metadata_available: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

class ProcessingSummary(BaseModel):
    stages_completed: List[str]
    stages_failed: List[str]
    duration_seconds: float
    tags_generated: int
    pii_detected: bool
    nsfw_flagged: bool

class EnrichmentEvent(BaseModel):
    event_type: str
    document_id: str
    source_asset_id: str | None = None
    run_id: str | None = None
    metadata_version: str
    model_version: str
    enrichment_version: str
    confidence_aggregate: float
    processing_summary: ProcessingSummary
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
        document_id="123",
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
