"""Persistent, queryable ingestion-run and per-source processing history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ingestion.services.database import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("connectors.id"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    enumeration_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enumeration_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enumerated_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    metadata_files_skipped: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    terminal_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    succeeded_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    transient_retry_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes_processed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    enumeration_seconds: Mapped[float | None] = mapped_column(Float)
    peak_memory_bytes: Mapped[int | None] = mapped_column(BigInteger)
    enumeration_stats: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_detail: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list["IngestionRunItem"]] = relationship(
        "IngestionRunItem", back_populates="run", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'enumerating', 'processing', 'completed', "
            "'completed_with_errors', 'failed')",
            name="ck_ingestion_runs_status",
        ),
        Index("idx_ingestion_runs_connector_triggered", "connector_id", "triggered_at"),
        Index("idx_ingestion_runs_status", "status"),
    )


class IngestionRunItem(Base):
    """One source reference processed during one trigger run.

    The composite primary key makes Kafka replay idempotent: a terminal item
    can never increment the parent run counters twice.
    """

    __tablename__ = "ingestion_run_items"

    run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), primary_key=True
    )
    source_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    document_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )
    source_asset_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_assets.id"), nullable=True
    )
    outcome: Mapped[str | None] = mapped_column(String(32))
    enumerated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    bytes_processed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    stage_seconds: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text)

    run: Mapped[IngestionRun] = relationship("IngestionRun", back_populates="items")

    __table_args__ = (
        Index("idx_ingestion_run_items_document", "document_id"),
        Index("idx_ingestion_run_items_source_asset", "source_asset_id"),
        Index("idx_ingestion_run_items_outcome", "run_id", "outcome"),
    )
