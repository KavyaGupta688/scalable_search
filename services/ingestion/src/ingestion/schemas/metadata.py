"""Canonical system metadata schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SystemMetadata(BaseModel):
    """System-generated identity and source provenance for one document."""

    document_id: UUID
    checksum_sha256: str
    size_bytes: int = Field(ge=0)
    mime_type: str
    source_connector_id: UUID
    source_ref: str
    source_asset_id: UUID
    source_type: str
    source_etag: str | None = None
    source_version_id: str | None = None
    source_last_modified_at: datetime | None = None
    entitlement_id: UUID
    first_successful_ingested_at: datetime
    effective_expiry_at: datetime


class DocumentMetadata(BaseModel):
    """Validated canonical document fields before the database insert."""

    id: UUID
    checksum_sha256: str
    size_bytes: int
    mime_type: str
    source_connector_id: UUID
    source_ref: str
    source_asset_id: UUID
    source_type: str
    source_etag: str | None = None
    source_version_id: str | None = None
    source_last_modified_at: datetime | None = None
    entitlement_id: UUID
    first_successful_ingested_at: datetime
    effective_expiry_at: datetime

    @field_validator("checksum_sha256")
    @classmethod
    def validate_checksum_format(cls, value: str) -> str:
        if len(value) != 64 or not all(character in "0123456789abcdef" for character in value):
            raise ValueError("checksum_sha256 must be a 64-character lowercase hexadecimal string")
        return value

    @field_validator("size_bytes")
    @classmethod
    def validate_size_positive(cls, value: int) -> int:
        if value < 0:
            raise ValueError("size_bytes must be non-negative")
        return value

    def to_orm_dict(self) -> dict:
        """Return only fields stored on ``documents``."""

        return self.model_dump(
            exclude={
                "first_successful_ingested_at",
                "effective_expiry_at",
                "source_asset_id",
                "source_type",
                "source_etag",
                "source_version_id",
                "source_last_modified_at",
            }
        )
