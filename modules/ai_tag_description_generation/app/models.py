"""
Layer 2 - Database Models
Defines the schema for task tracking and metadata storage.
Using JSON (JSONB via Postgres) allows flexible schemas as model outputs evolve.
"""
import uuid

from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import func
from app.db import Base

STATUS_QUEUED = "queued"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_PARTIAL = "partial"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_FAILED_TERMINAL = "failed_terminal"
STATUS_PENDING = "pending"

class EnrichmentTask(Base):
    __tablename__ = "enrichment_tasks"

    file_id = Column(String(255), primary_key=True)
    status = Column(String(20), default=STATUS_QUEUED)
    current_stage = Column(String(50), nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    stage_results = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    locked_by = Column(String(255), nullable=True)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    storage_path = Column(Text)
    file_type = Column(String(50))
    checksum = Column(String(128))
    source_metadata = Column(JSON, nullable=True)

class DocumentEnrichmentMetadata(Base):
    """AI output for a document owned by the existing ingestion schema."""
    __tablename__ = "document_enrichment_metadata"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(PG_UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    model_version = Column(String(100), nullable=False)
    enrichment_version = Column(String(50), nullable=False)
    metadata_version = Column(String(50), nullable=False, default="1.0")
    generated_tags = Column(JSONB)
    short_description = Column(Text)
    long_description = Column(Text)
    search_description = Column(Text)
    accessibility_description = Column(Text)
    ocr_text = Column(Text)
    transcribed_text = Column(Text)
    native_document_text = Column(Text)
    privacy_safety_labels = Column(JSONB)
    restricted_metadata = Column(JSONB)
    quality_labels = Column(JSONB)
    confidence_scores = Column(JSONB)
    model_versions = Column(JSONB)
    status = Column(String(20), default=STATUS_PENDING, name="enrichment_status")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('file_id', 'model_version', 'enrichment_version', name='uix_document_enrichment_version'),
    )

if __name__ == "__main__":
    print("Models layer loaded.")
