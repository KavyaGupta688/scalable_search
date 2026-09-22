"""
Pydantic schemas for source connector API requests and responses.

These schemas are the API boundary — they validate what goes in and
control what comes out. Raw secrets never appear in responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class S3ConnectorFields(BaseModel):
    """S3-specific connector configuration fields."""

    endpoint_url: str = Field(..., description="S3-compatible endpoint URL")
    bucket: str = Field(..., description="Source bucket name")
    auth_mode: Literal["static_keys", "aws_assume_role", "anonymous"] = Field(
        "static_keys",
        description="Development static keys or production AWS STS AssumeRole",
    )
    access_key: Optional[str] = Field(None, description="AWS access key ID (static_keys only)")
    metadata_mode: Literal["required", "optional", "none"] = "required"
    secret_key: Optional[str] = Field(None, description="AWS secret access key (static_keys only)")
    role_arn: Optional[str] = Field(None, description="Vendor IAM role ARN (aws_assume_role only)")
    external_id: Optional[str] = Field(
        None,
        description="Cross-account External ID stored only in Vault",
    )
    session_duration_seconds: int = Field(
        3600,
        ge=900,
        le=43200,
        description="Requested STS session duration, subject to the role maximum",
    )
    addressing_style: Literal["path", "virtual"] = Field(
        "path",
        description="S3 addressing style: 'path' or 'virtual'",
    )
    signature_version: Literal["s3v4", "s3"] = Field(
        "s3v4",
        description="S3 signature version: 's3v4' (SigV4) or 's3' (SigV2)",
    )
    prefix: str = Field(
        "",
        max_length=1024,
        description="Only enumerate objects whose key begins with this prefix. Empty means the whole bucket.",
    )
    max_objects: Optional[int] = Field(
        None,
        ge=1,
        description="Hard safety cap for this run. Null means no object-count cap.",
    )
    page_size: int = Field(
        1000,
        ge=1,
        le=1000,
        description="S3 ListObjectsV2 keys per request. 1000 minimizes list requests.",
    )

    @model_validator(mode="after")
    def validate_authentication(self):
        if self.auth_mode == "anonymous":
            if self.access_key or self.secret_key or self.role_arn or self.external_id:
                raise ValueError("Public bucket access must not include credentials or a role")
            return self
        if self.auth_mode == "static_keys":
            if not self.access_key or not self.secret_key:
                raise ValueError("access_key and secret_key are required for static_keys")
            if self.role_arn:
                raise ValueError("role_arn is only valid for aws_assume_role")
        else:
            if not self.role_arn:
                raise ValueError("role_arn is required for aws_assume_role")
            if self.access_key or self.secret_key:
                raise ValueError(
                    "Do not send vendor access keys with aws_assume_role; use the workload's AWS credential chain"
                )
        return self


class S3EnumerationScopeUpdate(BaseModel):
    """Change S3 enumeration scope without re-entering credentials."""

    prefix: str = Field("", max_length=1024)
    max_objects: Optional[int] = Field(None, ge=1)
    page_size: int = Field(1000, ge=1, le=1000)


class S3AuthenticationUpdate(BaseModel):
    """Replace one connector's S3 authentication without exposing old secrets."""

    auth_mode: Literal["static_keys", "aws_assume_role", "anonymous"]
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    role_arn: Optional[str] = None
    external_id: Optional[str] = None
    session_duration_seconds: int = Field(3600, ge=900, le=43200)

    @model_validator(mode="after")
    def validate_authentication(self):
        if self.auth_mode == "anonymous":
            if self.access_key or self.secret_key or self.role_arn or self.external_id:
                raise ValueError("Public bucket access must not include credentials or a role")
            return self
        if self.auth_mode == "static_keys":
            if not self.access_key or not self.secret_key:
                raise ValueError("access_key and secret_key are required for static_keys")
            if self.role_arn:
                raise ValueError("role_arn is only valid for aws_assume_role")
        else:
            if not self.role_arn:
                raise ValueError("role_arn is required for aws_assume_role")
            if self.access_key or self.secret_key:
                raise ValueError("Static keys cannot be supplied with aws_assume_role")
        return self


class NASConnectorFields(BaseModel):
    """NAS-specific connector configuration fields."""

    protocol: Literal["SMB", "NFS"] = Field(..., description="NAS protocol: SMB or NFS")
    mount_path: str = Field(..., description="Share path (e.g., '\\\\server\\share' for SMB, 'server:/path' for NFS)")
    username: Optional[str] = Field(None, description="NAS username")
    password: Optional[str] = Field(None, description="NAS password")
    domain: Optional[str] = Field(None, description="SMB domain (optional)")
    max_files: Optional[int] = Field(
        None,
        ge=1,
        description="Hard safety cap for NAS enumeration. Null permits the full configured path.",
    )

    @model_validator(mode="after")
    def validate_smb(self):
        if self.protocol == "SMB":
            normalized = self.mount_path.strip().replace("/", "\\").rstrip("\\")
            parts = normalized[2:].split("\\")
            if not normalized.startswith("\\\\") or len(parts) < 2 or any(p in ("", ".", "..") or ":" in p for p in parts):
                raise ValueError("SMB mount_path must be a UNC server/share path without traversal")
            if not self.username or not self.password:
                raise ValueError("SMB username and password are required")
            self.mount_path = normalized
        return self


class ConnectorCreate(BaseModel):
    """Request schema for creating a new connector."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable connector name",
    )
    source_type: Literal["S3", "NAS_SMB", "NAS_NFS"] = Field(..., description="Source type")

    # S3 fields (required when source_type == 'S3')
    s3: Optional[S3ConnectorFields] = Field(None, description="S3-specific configuration")

    # NAS fields (required when source_type in ('NAS_SMB', 'NAS_NFS'))
    nas: Optional[NASConnectorFields] = Field(None, description="NAS-specific configuration")

    @model_validator(mode="after")
    def validate_source_configuration(self):
        """Validate that the correct sub-fields are present for the source type."""
        if self.source_type == "S3" and self.s3 is None:
            raise ValueError("S3 configuration is required when source_type is 'S3'")
        if self.source_type in ("NAS_SMB", "NAS_NFS") and self.nas is None:
            raise ValueError("NAS configuration is required when source_type is 'NAS_SMB' or 'NAS_NFS'")
        if self.source_type == "S3" and self.nas is not None:
            raise ValueError("NAS configuration cannot be supplied for an S3 connector")
        if self.source_type != "S3" and self.s3 is not None:
            raise ValueError("S3 configuration cannot be supplied for a NAS connector")
        expected_protocol = {"NAS_SMB": "SMB", "NAS_NFS": "NFS"}.get(self.source_type)
        if self.nas is not None and expected_protocol and self.nas.protocol != expected_protocol:
            raise ValueError(f"nas.protocol must be '{expected_protocol}' when source_type is '{self.source_type}'")
        return self


class ConnectorResponse(BaseModel):
    archived_at: datetime | None = None
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
    s3_auth_mode: Optional[str] = None
    s3_role_arn: Optional[str] = None
    s3_session_duration_seconds: Optional[int] = None
    s3_prefix: Optional[str] = None
    source_metadata_mode: str = "required"
    enumeration_max_objects: Optional[int] = None
    enumeration_page_size: Optional[int] = None
    status: str
    # NOTE: secret_path is intentionally excluded from the response.


class ConnectorTestResponse(BaseModel):
    """Response schema for connector test results."""

    connector_id: UUID
    status: str
    message: str
    tested_at: datetime
