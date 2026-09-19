"""API representations for durable ingestion-run history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StageTimingResponse(BaseModel):
    cumulative_seconds: float
    sample_count: int
    mean_seconds: float | None


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    connector_id: UUID
    source_type: str
    status: str
    triggered_at: datetime
    enumeration_started_at: datetime | None
    enumeration_completed_at: datetime | None
    completed_at: datetime | None
    enumerated_count: int
    metadata_files_skipped: int
    terminal_count: int
    succeeded_count: int
    duplicate_count: int
    skipped_count: int
    rejected_count: int
    failed_count: int
    transient_retry_count: int
    bytes_processed: int
    enumeration_seconds: float | None
    peak_memory_bytes: int | None
    enumeration_stats: dict = Field(default_factory=dict)
    error_detail: str | None
    elapsed_seconds: float | None = None
    mib_per_second: float | None = None
    objects_per_second: float | None = None
    stage_timings: dict[str, StageTimingResponse] = Field(default_factory=dict)


class IngestionRunItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: UUID
    source_ref: str
    job_id: str
    document_id: UUID | None
    source_asset_id: UUID | None
    outcome: str | None
    enumerated_at: datetime | None
    processing_started_at: datetime | None
    completed_at: datetime | None
    attempts: int
    bytes_processed: int
    stage_seconds: dict = Field(default_factory=dict)
    last_error: str | None
