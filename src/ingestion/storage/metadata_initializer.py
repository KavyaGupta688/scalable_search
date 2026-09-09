from __future__ import annotations

import uuid_utils
from datetime import datetime
from uuid import UUID
from typing import Optional

from ingestion.schemas.job import JobDescriptor
from ingestion.schemas.metadata import SystemMetadata

def create_system_metadata(
    checksum: str, 
    size_bytes: int, 
    mime_type: str, 
    storage_path: str, 
    job: JobDescriptor, 
    entitlement_id: UUID,
    bucket_name: str,
    first_successful_ingested_at: Optional[datetime] = None,
    effective_expiry_at: Optional[datetime] = None,
    object_version_id: Optional[str] = None,
) -> SystemMetadata:
    if first_successful_ingested_at is None or effective_expiry_at is None:
        raise ValueError(
            "first_successful_ingested_at and effective_expiry_at are required"
        )
    return SystemMetadata(
        # uuid_utils.UUID is a distinct type from uuid.UUID.  Convert through
        # its canonical string so Pydantic/SQLAlchemy receive the standard
        # UUID object expected by the schemas and PostgreSQL dialect.
        document_id=UUID(str(uuid_utils.uuid7())),
        entitlement_id=entitlement_id,
        bucket_name=bucket_name,
        first_successful_ingested_at=first_successful_ingested_at,
        effective_expiry_at=effective_expiry_at,
        object_version_id=object_version_id,
        retention_status="active",
        checksum_sha256=checksum,
        size_bytes=size_bytes,
        mime_type=mime_type,
        storage_path=storage_path,
        source_connector_id=job.connector_id,
        source_ref=job.source_ref,
    )
