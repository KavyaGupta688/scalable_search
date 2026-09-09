"""
Pydantic schemas for the metadata pipeline.

Three-stage pipeline:
  1. TikaMetadata: raw extracted metadata from Tika (variable fields per file type)
  2. SystemMetadata: always-present system-generated fields
  3. DocumentMetadata: merged + validated canonical schema for DB persistence
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class TikaMetadata(BaseModel):
    """
    Raw metadata extracted by Apache Tika.

    Fields vary by file type — EXIF for images, PDF properties for PDFs, etc.
    An empty dict is valid (file had no embedded metadata).
    """

    content_type: Optional[str] = Field(None, alias="Content-Type")
    creator: Optional[str] = Field(None, alias="dc:creator")
    title: Optional[str] = Field(None, alias="dc:title")
    description: Optional[str] = Field(None, alias="dc:description")
    created_date: Optional[str] = Field(None, alias="dcterms:created")
    modified_date: Optional[str] = Field(None, alias="dcterms:modified")
    page_count: Optional[str] = Field(None, alias="xmpTPg:NPages")

    # EXIF fields (images)
    image_width: Optional[str] = Field(None, alias="tiff:ImageWidth")
    image_height: Optional[str] = Field(None, alias="tiff:ImageLength")
    camera_make: Optional[str] = Field(None, alias="tiff:Make")
    camera_model: Optional[str] = Field(None, alias="tiff:Model")
    gps_latitude: Optional[str] = Field(None, alias="geo:lat")
    gps_longitude: Optional[str] = Field(None, alias="geo:long")

    # Audio/video fields
    duration: Optional[str] = Field(None, alias="xmpDM:duration")
    audio_sample_rate: Optional[str] = Field(None, alias="xmpDM:audioSampleRate")

    # Catch-all for any additional Tika fields
    extra: dict[str, Any] = Field(default_factory=dict)

    model_config = {"populate_by_name": True, "extra": "allow"}


class SystemMetadata(BaseModel):
    """
    System-generated metadata that always exists regardless of file type.

    Produced by the metadata initializer from known facts about the ingestion.
    """

    document_id: UUID = Field(..., description="UUIDv7 document identifier")
    checksum_sha256: str = Field(..., description="SHA-256 hex digest")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    mime_type: str = Field(..., description="Validated MIME type from libmagic")
    storage_path: str = Field(..., description="MinIO object key")
    source_connector_id: UUID = Field(..., description="Source connector ID")
    source_ref: str = Field(..., description="Source reference path")
    entitlement_id: UUID
    bucket_name: str
    first_successful_ingested_at: datetime
    effective_expiry_at: datetime
    object_version_id: Optional[str] = None
    retention_status: str = "active"


class DocumentMetadata(BaseModel):
    """
    Canonical merged metadata schema.

    This is the final validated form before SQLAlchemy INSERT.
    Merges SystemMetadata (always present) with TikaMetadata (optional).
    Pydantic validates in memory; it does not touch the database.
    """

    # System fields (always present)
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
    retention_status: str = "active"

    # Tika-extracted fields (optional, normalized)
    tika_metadata: Optional[dict[str, Any]] = None

    @field_validator("checksum_sha256")
    @classmethod
    def validate_checksum_format(cls, v: str) -> str:
        """Ensure checksum is a valid 64-char hex SHA-256 digest."""
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError(
                f"checksum_sha256 must be a 64-character lowercase hex string, got '{v[:20]}...'"
            )
        return v

    @field_validator("size_bytes")
    @classmethod
    def validate_size_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError(f"size_bytes must be non-negative, got {v}")
        return v

    def to_orm_dict(self) -> dict:
        """Convert to a dict suitable for SQLAlchemy model construction."""
        # These values remain in the in-memory/Kafka contract, but their
        # authoritative database home is license_entitlements.
        return self.model_dump(exclude={
            "first_successful_ingested_at",
            "effective_expiry_at",
        })
