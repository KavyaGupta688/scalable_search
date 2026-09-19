"""
Layer 2 - Database Models
Defines the schema for task tracking and metadata storage.
Using JSON (JSONB via Postgres) allows flexible schemas as model outputs evolve.
"""
import uuid

from sqlalchemy import BigInteger, CheckConstraint, Column, String, Integer, Text, DateTime, JSON, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.sql import func
from modules.ai_tag_description_generation.app.db import Base

STATUS_QUEUED = "queued"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
STATUS_PARTIAL = "partial"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_FAILED_TERMINAL = "failed_terminal"
STATUS_QUEUE_FAILED = "queue_failed"
STATUS_PENDING = "pending"

class EnrichmentTask(Base):
    __tablename__ = "enrichment_tasks"

    document_id = Column(PG_UUID(as_uuid=False), primary_key=True)
    status = Column(String(20), nullable=False, default=STATUS_QUEUED, server_default=STATUS_QUEUED)
    current_stage = Column(String(50), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default=text("0"))
    max_retries = Column(Integer, nullable=False, default=3, server_default=text("3"))
    stage_results = Column(JSON, nullable=False, default=dict, server_default=text("'{}'::json"))
    error_message = Column(Text, nullable=True)
    locked_by = Column(String(255), nullable=True)
    lock_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    run_id = Column(PG_UUID(as_uuid=True), nullable=True)
    source_asset_id = Column(PG_UUID(as_uuid=True), nullable=True)
    entitlement_id = Column(PG_UUID(as_uuid=True), nullable=True)
    source_type = Column(String(16), nullable=True)
    source_ref = Column(Text, nullable=True)
    mime_type = Column(String(255), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    checksum_sha256 = Column(String(64), nullable=True)
    vendor_metadata = Column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','queue_failed','in_progress','completed','partial','needs_review','failed_terminal')",
            name="ck_enrichment_tasks_status",
        ),
    )

class DocumentEnrichmentMetadata(Base):
    """AI output for a document owned by the existing ingestion schema."""
    __tablename__ = "document_enrichment_metadata"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The database FK is created by Alembic revision 002. It is intentionally
    # not declared in ORM metadata because the referenced ingestion table is
    # externally owned and must never be created by Base.metadata.create_all().
    document_id = Column(PG_UUID(as_uuid=True), nullable=False)
    source_asset_id = Column(PG_UUID(as_uuid=True), nullable=True)
    run_id = Column(PG_UUID(as_uuid=True), nullable=True)
    correlation_id = Column(Text, nullable=True)
    model_name = Column(Text, nullable=False, default="ai_tag_description_generation", server_default="ai_tag_description_generation")
    model_version = Column(Text, nullable=False)
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
        UniqueConstraint('document_id', 'model_name', 'model_version', 'enrichment_version', name='uix_document_enrichment_version'),
    )

if __name__ == "__main__":
    print("Models layer loaded.")
