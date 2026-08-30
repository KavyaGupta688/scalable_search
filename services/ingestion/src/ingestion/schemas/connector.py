"""
Pydantic schemas for source connector API requests and responses.

These schemas are the API boundary — they validate what goes in and
control what comes out. Raw secrets never appear in responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class S3ConnectorFields(BaseModel):
    """S3-specific connector configuration fields."""

    endpoint_url: str = Field(..., description="S3-compatible endpoint URL")
    bucket: str = Field(..., description="Source bucket name")
    access_key: str = Field(..., description="AWS access key ID")
    secret_key: str = Field(..., description="AWS secret access key")
    addressing_style: Literal["path", "virtual"] = Field(
        "path",
        description="S3 addressing style: 'path' or 'virtual'",
    )
    signature_version: Literal["s3v4", "s3"] = Field(
        "s3v4",
        description="S3 signature version: 's3v4' (SigV4) or 's3' (SigV2)",
    )


class NASConnectorFields(BaseModel):
    """NAS-specific connector configuration fields."""

    protocol: Literal["SMB", "NFS"] = Field(
        ..., description="NAS protocol: SMB or NFS"
    )
    mount_path: str = Field(
        ..., description="Share path (e.g., '\\\\server\\share' for SMB, 'server:/path' for NFS)"
    )
    username: Optional[str] = Field(None, description="NAS username")
    password: Optional[str] = Field(None, description="NAS password")
    domain: Optional[str] = Field(None, description="SMB domain (optional)")


class ConnectorCreate(BaseModel):
    """Request schema for creating a new connector."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable connector name",
    )
    source_type: Literal["S3", "NAS_SMB", "NAS_NFS"] = Field(
        ..., description="Source type"
    )

    # S3 fields (required when source_type == 'S3')
    s3: Optional[S3ConnectorFields] = Field(
        None, description="S3-specific configuration"
    )

    # NAS fields (required when source_type in ('NAS_SMB', 'NAS_NFS'))
    nas: Optional[NASConnectorFields] = Field(
        None, description="NAS-specific configuration"
    )

    def model_post_init(self, __context) -> None:
        """Validate that the correct sub-fields are present for the source type."""
        if self.source_type == "S3" and self.s3 is None:
            raise ValueError("S3 configuration is required when source_type is 'S3'")
        if self.source_type in ("NAS_SMB", "NAS_NFS") and self.nas is None:
            raise ValueError(
                "NAS configuration is required when source_type is 'NAS_SMB' or 'NAS_NFS'"
            )


class ConnectorResponse(BaseModel):
    """Response schema for connector details. Never includes raw secrets."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: str
    endpoint_url: Optional[str] = None
    bucket: Optional[str] = None
    mount_path: Optional[str] = None
    addressing_style: Optional[str] = None
    signature_version: Optional[str] = None
    status: str
    created_by: UUID
    created_at: datetime
    last_verified_at: Optional[datetime] = None

    # NOTE: secret_path is intentionally excluded from the response.


class ConnectorTestResponse(BaseModel):
    """Response schema for connector test results."""

    connector_id: UUID
    status: str
    message: str
    tested_at: datetime
