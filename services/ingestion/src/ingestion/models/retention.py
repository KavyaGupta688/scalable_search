"""Immutable licence entitlements and append-only retention audit events."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ingestion.services.database import Base


class LicenseEntitlement(Base):
    """Authoritative, revisioned licence clock for one content identity."""

    __tablename__ = "license_entitlements"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    license_subject_id: Mapped[str] = mapped_column(Text, nullable=False)
    license_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_code: Mapped[str] = mapped_column(
        String(64), nullable=False, default="calendar-3y-v1"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_entitlement_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("license_entitlements.id"), nullable=True
    )
    approval_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    documents: Mapped[list["Document"]] = relationship(  # noqa: F821
        "Document", back_populates="entitlement"
    )

    __table_args__ = (
        UniqueConstraint(
            "license_subject_id",
            "revision",
            name="uq_entitlements_subject_revision",
        ),
    )
