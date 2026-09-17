"""
Canonical document and physical source-asset ORM models.

Document: canonical metadata record for every unique SHA-256 content identity.
SourceAsset: one physical S3/SMB/NFS location containing that content.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ingestion.services.database import Base


class Document(Base):
    """
    Canonical metadata record for an ingested file.

    One row per unique SHA-256 checksum. File bytes remain in vendor storage;
    source_assets records every physical location containing those bytes.
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
    source_connector_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("connectors.id"),
        nullable=False,
    )
    source_ref: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    entitlement_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("license_entitlements.id"), nullable=False
    )
    # Relationships
    source_assets: Mapped[list[SourceAsset]] = relationship(
        "SourceAsset",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    entitlement: Mapped[LicenseEntitlement] = relationship(  # noqa: F821
        "LicenseEntitlement", back_populates="documents"
    )
    structured_metadata: Mapped[list[DocumentSourceMetadata]] = relationship(
        "DocumentSourceMetadata",
        back_populates="document",
    )

    __table_args__ = (
        UniqueConstraint("checksum_sha256", name="uq_documents_checksum"),
        Index("idx_documents_checksum", "checksum_sha256", unique=True),
        Index("idx_documents_mime_type", "mime_type"),
        Index("idx_documents_source_connector", "source_connector_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, mime={self.mime_type}, "
            f"size={self.size_bytes}, checksum={self.checksum_sha256[:12]}...)>"
        )


class SourceAsset(Base):
    """
    A physical vendor-owned location for canonical document content.

    Multiple rows may point at one document when byte-identical files exist
    in different connectors or paths. No vendor file is deleted as deduplication.
    """

    __tablename__ = "source_assets"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
    )
    document_id: Mapped[UUID] = mapped_column(
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
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_version_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    availability_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="available"
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    document: Mapped[Document] = relationship(
        "Document",
        back_populates="source_assets",
    )
    structured_metadata: Mapped[DocumentSourceMetadata | None] = relationship(
        "DocumentSourceMetadata",
        back_populates="source_asset",
        cascade="all, delete-orphan",
        uselist=False,
    )

    __table_args__ = (
        Index("idx_source_assets_document", "document_id"),
        Index(
            "uq_source_assets_active_location",
            "source_connector_id",
            "source_ref",
            unique=True,
            postgresql_where=(availability_status == "available"),
        ),
        Index(
            "idx_source_assets_connector_availability",
            "source_connector_id",
            "availability_status",
        ),
        CheckConstraint(
            "availability_status IN ('available', 'changed', 'missing', 'inaccessible')",
            name="ck_source_assets_availability_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<SourceAsset(id={self.id}, document={self.document_id}, source={self.source_ref})>"


class DocumentSourceMetadata(Base):
    """Structured metadata supplied by vendor manifest and sidecar files."""

    __tablename__ = "document_metadata"

    source_asset_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_assets.id"), primary_key=True
    )
    document_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    metadata_formats: Mapped[list[str]] = mapped_column(ARRAY(String(32)), nullable=False)
    metadata_source_refs: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    external_asset_id: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    primary_category: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    categories: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    brand: Mapped[str | None] = mapped_column(Text)
    contributor_id: Mapped[str | None] = mapped_column(Text)
    additional_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    document: Mapped[Document] = relationship(
        "Document", back_populates="structured_metadata"
    )
    source_asset: Mapped[SourceAsset] = relationship(
        "SourceAsset", back_populates="structured_metadata"
    )

    __table_args__ = (
        Index("idx_document_metadata_document", "document_id"),
        Index("idx_document_metadata_external_asset_id", "external_asset_id"),
        Index("idx_document_metadata_category", "primary_category"),
        Index("idx_document_metadata_contributor", "contributor_id"),
    )
