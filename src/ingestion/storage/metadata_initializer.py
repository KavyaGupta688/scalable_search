from __future__ import annotations

import uuid_utils
from datetime import datetime, timezone
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
    created_by: Optional[UUID] = None
) -> SystemMetadata:
    return SystemMetadata(
        document_id=uuid_utils.uuid7(),
        created_at=datetime.now(timezone.utc),
        created_by=created_by,
        checksum_sha256=checksum,
        size_bytes=size_bytes,
        mime_type=mime_type,
        storage_path=storage_path,
        source_connector_id=job.connector_id,
        source_ref=job.source_ref,
    )
