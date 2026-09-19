"""
Pydantic schemas for document API responses and search parameters.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ingestion.schemas.source_metadata import StructuredSourceMetadata


class DocumentSourceMetadataResponse(StructuredSourceMetadata):
    """Vendor metadata associated with one physical source asset."""

    source_asset_id: UUID


class DocumentResponse(BaseModel):
    """Response schema for document metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    checksum_sha256: str
    size_bytes: int
    mime_type: str
    source_connector_id: UUID
    source_ref: str
    entitlement_id: UUID
    first_successful_ingested_at: datetime
    effective_expiry_at: datetime
    entitlement_status: str
    metadata: list[DocumentSourceMetadataResponse] = Field(default_factory=list)


class DocumentSearchParams(BaseModel):
    """Query parameters for document search."""

    mime_type: str | None = Field(None, description="Filter by MIME type")
    source_connector_id: UUID | None = Field(None, description="Filter by source connector")
    run_id: UUID | None = Field(None, description="Filter by ingestion run")
    date_from: datetime | None = Field(None, description="Filter by creation date (from)")
    date_to: datetime | None = Field(None, description="Filter by creation date (to)")
    checksum: str | None = Field(None, description="Search by exact SHA-256 checksum")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(50, ge=1, le=500, description="Results per page")


class SourceAssetResponse(BaseModel):
    """One physical vendor-owned location for a document."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    source_connector_id: UUID
    source_ref: str
    size_bytes: int
    etag: str | None = None
    source_version_id: str | None = None
    source_last_modified_at: datetime | None = None
    availability_status: str
    last_verified_at: datetime | None = None


class DocumentSourceResponse(BaseModel):
    """Resolved direct-source access without exposing stored credentials."""

    document_id: UUID
    source_asset: SourceAssetResponse
    access_mode: str
    access_url: str | None = None
    expires_in_seconds: int | None = None
