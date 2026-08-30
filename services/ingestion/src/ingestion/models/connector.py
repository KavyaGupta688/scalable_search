"""
Connector ORM model.

Represents a configured data source (S3 bucket or NAS share).
Credentials are NEVER stored here — only a Vault path reference.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, String, Text
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
        Enum(SourceType, name="source_type_enum", create_constraint=False),
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
        Enum(ConnectorStatus, name="connector_status_enum", create_constraint=False),
        nullable=False,
        default=ConnectorStatus.UNVERIFIED,
    )

    # Audit fields
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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
    )

    def __repr__(self) -> str:
        return (
            f"<Connector(id={self.id}, name='{self.name}', "
            f"type={self.source_type}, status={self.status})>"
        )
