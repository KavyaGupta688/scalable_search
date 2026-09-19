from __future__ import annotations

from datetime import datetime
from uuid import UUID

import uuid_utils

from ingestion.schemas.job import JobDescriptor
from ingestion.schemas.metadata import SystemMetadata


def create_system_metadata(
    checksum: str,
    size_bytes: int,
    mime_type: str,
    job: JobDescriptor,
    entitlement_id: UUID,
    source_asset_id: UUID,
    first_successful_ingested_at: datetime | None = None,
    effective_expiry_at: datetime | None = None,
) -> SystemMetadata:
    if first_successful_ingested_at is None or effective_expiry_at is None:
        raise ValueError("first_successful_ingested_at and effective_expiry_at are required")
    return SystemMetadata(
        # uuid_utils.UUID is a distinct type from uuid.UUID.  Convert through
        # its canonical string so Pydantic/SQLAlchemy receive the standard
        # UUID object expected by the schemas and PostgreSQL dialect.
        document_id=UUID(str(uuid_utils.uuid7())),
        entitlement_id=entitlement_id,
        source_asset_id=source_asset_id,
        source_type=job.source_type,
        source_etag=job.etag,
        source_version_id=job.version_id,
        source_last_modified_at=job.mtime,
        first_successful_ingested_at=first_successful_ingested_at,
        effective_expiry_at=effective_expiry_at,
        checksum_sha256=checksum,
        size_bytes=size_bytes,
        mime_type=mime_type,
        source_connector_id=job.connector_id,
        source_ref=job.source_ref,
    )
