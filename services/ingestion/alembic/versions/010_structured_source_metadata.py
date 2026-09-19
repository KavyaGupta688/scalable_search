"""Replace Tika JSONB with structured vendor-supplied metadata.

Revision ID: 010
Revises: 009
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op


revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_metadata",
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metadata_formats", postgresql.ARRAY(sa.String(length=32)), nullable=False),
        sa.Column("metadata_source_refs", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("asset_id", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("primary_category", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("categories", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("declared_file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("declared_mime_type", sa.Text(), nullable=True),
        sa.Column("camera_make", sa.Text(), nullable=True),
        sa.Column("camera_model", sa.Text(), nullable=True),
        sa.Column("location_name", sa.Text(), nullable=True),
        sa.Column("gps_lat", sa.Numeric(10, 7), nullable=True),
        sa.Column("gps_lon", sa.Numeric(10, 7), nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("download_count", sa.BigInteger(), nullable=True),
        sa.Column("brand", sa.Text(), nullable=True),
        sa.Column("image_type", sa.String(length=32), nullable=True),
        sa.Column("contributor_id", sa.Text(), nullable=True),
        sa.Column("target_path", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["source_assets.id"]),
        sa.PrimaryKeyConstraint("source_asset_id"),
    )
    op.create_index("idx_document_metadata_document", "document_metadata", ["document_id"])
    op.create_index("idx_document_metadata_asset_id", "document_metadata", ["asset_id"])
    op.create_index(
        "idx_document_metadata_category", "document_metadata", ["primary_category"]
    )
    op.create_index(
        "idx_document_metadata_contributor", "document_metadata", ["contributor_id"]
    )

    # Tika output is deliberately not copied: it is unstructured, considered
    # irrelevant by the client, and is replaced by authoritative source metadata.
    op.drop_column("documents", "tika_metadata")


def downgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "tika_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.drop_index("idx_document_metadata_contributor", table_name="document_metadata")
    op.drop_index("idx_document_metadata_category", table_name="document_metadata")
    op.drop_index("idx_document_metadata_asset_id", table_name="document_metadata")
    op.drop_index("idx_document_metadata_document", table_name="document_metadata")
    op.drop_table("document_metadata")
