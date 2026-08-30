"""
Document and DuplicateLink ORM models.

Document: canonical metadata record for every unique ingested file.
DuplicateLink: lightweight reference when a duplicate is detected.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ingestion.services.database import Base


class Document(Base):
    """
    Canonical metadata record for an ingested file.

    One row per unique SHA-256 checksum. The storage_path points to the
    deduplicated object in MinIO. The unique index on checksum_sha256
    enforces deduplication at the database level.
    """

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )
    checksum_sha256: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    mime_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_connector_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("connectors.id"),
        nullable=True,
    )
    source_ref: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Audit fields
    created_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # --- Extended metadata (from Tika + system metadata) ---
    # Stored as a JSONB column for flexibility across file types.
    # The Pydantic normalizer validates before this is written.
    tika_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    duplicate_links: Mapped[list[DuplicateLink]] = relationship(
        "DuplicateLink",
        back_populates="original_document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("checksum_sha256", name="uq_documents_checksum"),
        Index("idx_documents_checksum", "checksum_sha256", unique=True),
        Index("idx_documents_mime_type", "mime_type"),
        Index("idx_documents_source_connector", "source_connector_id"),
        Index("idx_documents_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, mime={self.mime_type}, "
            f"size={self.size_bytes}, checksum={self.checksum_sha256[:12]}...)>"
        )


class DuplicateLink(Base):
    """
    Lightweight link record for duplicate files.

    When a file's SHA-256 matches an existing document, we abort the
    multipart upload and create this link instead of storing a second copy.
    """

    __tablename__ = "duplicate_links"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )
    original_document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
    )
    source_connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("connectors.id"),
        nullable=False,
    )
    source_ref: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    original_document: Mapped[Document] = relationship(
        "Document",
        back_populates="duplicate_links",
    )

    __table_args__ = (
        Index("idx_duplinks_original", "original_document_id"),
        Index("idx_duplinks_source_ref", "source_ref"),
    )

    def __repr__(self) -> str:
        return (
            f"<DuplicateLink(id={self.id}, "
            f"original={self.original_document_id}, ref={self.source_ref})>"
        )
