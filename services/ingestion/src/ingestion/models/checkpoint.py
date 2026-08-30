"""
EnumerationCheckpoint ORM model.

Persists the last enumeration position for each connector so that
a crash mid-enumeration resumes rather than re-scanning from zero.
S3 uses a continuation_token; NAS uses last_scanned_path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from ingestion.services.database import Base


class EnumerationCheckpoint(Base):
    """Resumable enumeration checkpoint per connector."""

    __tablename__ = "enumeration_checkpoints"

    connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("connectors.id"),
        primary_key=True,
    )
    # S3: continuation token from list_objects_v2
    continuation_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # NAS: last fully scanned path (for resume on crash)
    last_scanned_path: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<EnumerationCheckpoint(connector_id={self.connector_id}, "
            f"token={self.continuation_token[:20] + '...' if self.continuation_token else None}, "
            f"path={self.last_scanned_path})>"
        )
