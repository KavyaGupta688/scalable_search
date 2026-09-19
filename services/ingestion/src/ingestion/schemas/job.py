"""
Pydantic schemas for Kafka job messages.

JobDescriptor is the message schema published during enumeration and consumed by workers.
Both S3 and NAS jobs use the same schema — differentiated by source_type field.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class JobDescriptor(BaseModel):
    """
    A single file to be ingested, as discovered during enumeration.

    Published as a Kafka message to the ingestion-jobs topic.
    Both S3 and NAS produce these, differentiated by source_type.
    """

    source_type: Literal["S3", "NAS_SMB", "NAS_NFS"] = Field(
        ..., description="Source discriminator for worker dispatch"
    )
    connector_id: UUID = Field(..., description="ID of the source connector")
    run_id: UUID | None = Field(None, description="One trigger/backfill execution identifier")
    enumerated_at: datetime | None = Field(None, description="UTC time when this job was published by enumeration")
    source_ref: str = Field(
        ...,
        description=("Canonical source reference. S3: 'bucket/key', NAS: 'share/relative/path'"),
    )
    size_bytes: int | None = Field(None, description="File size in bytes (from source listing)")

    # S3-specific fields
    etag: str | None = Field(None, description="S3 ETag (S3 only)")
    version_id: str | None = Field(None, description="Stable source object version ID when available")
    bucket: str | None = Field(None, description="S3 bucket name (S3 only)")
    object_key: str | None = Field(None, description="S3 object key (S3 only)")

    # NAS-specific fields
    mount_path: str | None = Field(None, description="NAS share/mount path (NAS only)")
    relative_path: str | None = Field(None, description="Path relative to mount (NAS only)")
    mtime: datetime | None = Field(None, description="File modification time (NAS only)")

    # Provisional identifier for pre-hash dedup checks.
    # S3: ETag, NAS: hash(path + size + mtime)
    provisional_id: str = Field(..., description="Pre-hash provisional identifier")


class ProcessResult(str, enum.Enum):
    """Outcome of processing a single job."""

    SUCCESS = "success"
    DUPLICATE = "duplicate"
    SKIPPED = "skipped"  # Idempotent skip (already exists)
    REJECTED = "rejected"  # MIME type validation failure
    TRANSIENT_ERROR = "transient_error"
    PERMANENT_ERROR = "permanent_error"


@dataclass
class ProcessingStats:
    """Mutable timing/result detail populated during one worker attempt."""

    processing_started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    bytes_processed: int = 0
    stage_seconds: dict[str, float] = field(default_factory=dict)
    document_id: UUID | None = None
    source_asset_id: UUID | None = None
