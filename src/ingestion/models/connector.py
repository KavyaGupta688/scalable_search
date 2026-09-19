"""
Connector ORM model.

Represents a configured data source (S3 bucket or NAS share).
Credentials are NEVER stored here — only a Vault path reference.
"""

from __future__ import annotations

import enum
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ingestion.services.database import Base


class SourceType(str, enum.Enum):
    """Supported source connector types."""

    S3 = "S3"
    NAS_SMB = "NAS_SMB"
    NAS_NFS = "NAS_NFS"


class ConnectorStatus(str, enum.Enum):
    """Connector verification status."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    FAILED = "failed"


class Connector(Base):
    """
    A configured data source connector.

    Security invariant: This model has NO column for raw credentials.
    All secrets are stored in Vault; only the `secret_path` reference is persisted.
    """

    __tablename__ = "connectors"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_type: Mapped[SourceType] = mapped_column(
        Enum(
            SourceType,
            name="source_type_enum",
            create_constraint=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
    )

    # S3-specific fields (nullable for NAS connectors)
    endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    bucket: Mapped[str | None] = mapped_column(Text, nullable=True)
    addressing_style: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # 'path' or 'virtual'
    signature_version: Mapped[str | None] = mapped_column(
        String(10), nullable=True
    )  # 's3v4' or 's3' (SigV2)
    s3_auth_mode: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="static_keys"
    )
    s3_role_arn: Mapped[str | None] = mapped_column(Text, nullable=True)
    s3_session_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=3600
    )
    # Enumeration scope.  A prefix and maximum object count make it possible
    # to run a bounded test without accidentally walking an entire bucket.
    # ``max_objects=None`` means the connector is allowed to scan the whole
    # configured prefix (the production default).
    s3_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    enumeration_max_objects: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True
    )
    enumeration_page_size: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # NAS-specific fields (nullable for S3 connectors)
    mount_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Vault reference — the ONLY place credentials are referenced.
    # This stores a path like "connectors/<uuid>" under the configured Vault mount.
    secret_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Status tracking
    status: Mapped[ConnectorStatus] = mapped_column(
        Enum(
            ConnectorStatus,
            name="connector_status_enum",
            create_constraint=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        nullable=False,
        default=ConnectorStatus.UNVERIFIED,
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('S3', 'NAS_SMB', 'NAS_NFS')",
            name="ck_connectors_source_type",
        ),
        CheckConstraint(
            "status IN ('verified', 'unverified', 'failed')",
            name="ck_connectors_status",
        ),
        CheckConstraint(
            "s3_auth_mode IS NULL OR s3_auth_mode IN ('static_keys', 'aws_assume_role')",
            name="ck_connectors_s3_auth_mode",
        ),
        CheckConstraint(
            "s3_session_duration_seconds IS NULL OR "
            "s3_session_duration_seconds BETWEEN 900 AND 43200",
            name="ck_connectors_s3_session_duration",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Connector(id={self.id}, name='{self.name}', "
            f"type={self.source_type}, status={self.status})>"
        )
