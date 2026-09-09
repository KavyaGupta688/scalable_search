"""
Pydantic schemas for document API responses and search parameters.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Response schema for document metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    checksum_sha256: str
    size_bytes: int
    mime_type: str
    storage_path: str
    source_connector_id: UUID
    source_ref: str
    entitlement_id: UUID
    bucket_name: str
    first_successful_ingested_at: datetime
    effective_expiry_at: datetime
    object_version_id: Optional[str] = None
    retention_status: str
    deleted_at: Optional[datetime] = None
    last_reconciled_at: Optional[datetime] = None
    tika_metadata: Optional[dict] = None


class DocumentSearchParams(BaseModel):
    """Query parameters for document search."""

    mime_type: Optional[str] = Field(None, description="Filter by MIME type")
    source_connector_id: Optional[UUID] = Field(
        None, description="Filter by source connector"
    )
    date_from: Optional[datetime] = Field(
        None, description="Filter by creation date (from)"
    )
    date_to: Optional[datetime] = Field(
        None, description="Filter by creation date (to)"
    )
    checksum: Optional[str] = Field(
        None, description="Search by exact SHA-256 checksum"
    )
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=500, description="Results per page")


class DocumentDownloadResponse(BaseModel):
    """Response schema for document download (presigned URL)."""

    document_id: UUID
    download_url: str
    expires_in_seconds: int
    filename: str
    mime_type: str
    size_bytes: int
