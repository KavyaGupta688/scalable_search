"""Align AI persistence with ingestion's zero-copy document contract.

Revision ID: 003_ingestion_zero_copy
Revises: 002_document_enrichment_metadata
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "003_ingestion_zero_copy"
down_revision = "002_document_enrichment_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("enrichment_tasks", "file_id", new_column_name="document_id")
    op.drop_column("enrichment_tasks", "storage_path")
    op.drop_column("enrichment_tasks", "file_type")
    op.drop_column("enrichment_tasks", "checksum")
    op.drop_column("enrichment_tasks", "source_metadata")
    op.add_column("enrichment_tasks", sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("source_type", sa.String(16), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("source_ref", sa.Text(), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("mime_type", sa.String(255), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("checksum_sha256", sa.String(64), nullable=True))
    op.add_column(
        "enrichment_tasks",
        sa.Column("vendor_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )

    op.drop_index("ix_document_enrichment_metadata_file_id", table_name="document_enrichment_metadata")
    op.drop_constraint("uix_document_enrichment_version", "document_enrichment_metadata", type_="unique")
    op.alter_column("document_enrichment_metadata", "file_id", new_column_name="document_id")
    op.add_column("document_enrichment_metadata", sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("document_enrichment_metadata", sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("document_enrichment_metadata", sa.Column("correlation_id", sa.Text(), nullable=True))
    op.add_column(
        "document_enrichment_metadata",
        sa.Column("model_name", sa.Text(), nullable=False, server_default="ai_tag_description_generation"),
    )
    op.create_unique_constraint(
        "uix_document_enrichment_version",
        "document_enrichment_metadata",
        ["document_id", "model_name", "model_version", "enrichment_version"],
    )
    op.create_index(
        "ix_document_enrichment_metadata_document_id",
        "document_enrichment_metadata",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_enrichment_metadata_document_id", table_name="document_enrichment_metadata")
    op.drop_constraint("uix_document_enrichment_version", "document_enrichment_metadata", type_="unique")
    op.drop_column("document_enrichment_metadata", "model_name")
    op.drop_column("document_enrichment_metadata", "correlation_id")
    op.drop_column("document_enrichment_metadata", "run_id")
    op.drop_column("document_enrichment_metadata", "source_asset_id")
    op.alter_column("document_enrichment_metadata", "document_id", new_column_name="file_id")
    op.create_unique_constraint(
        "uix_document_enrichment_version",
        "document_enrichment_metadata",
        ["file_id", "model_version", "enrichment_version"],
    )
    op.create_index("ix_document_enrichment_metadata_file_id", "document_enrichment_metadata", ["file_id"])

    op.drop_column("enrichment_tasks", "vendor_metadata")
    op.drop_column("enrichment_tasks", "checksum_sha256")
    op.drop_column("enrichment_tasks", "size_bytes")
    op.drop_column("enrichment_tasks", "mime_type")
    op.drop_column("enrichment_tasks", "source_ref")
    op.drop_column("enrichment_tasks", "source_type")
    op.drop_column("enrichment_tasks", "entitlement_id")
    op.drop_column("enrichment_tasks", "source_asset_id")
    op.drop_column("enrichment_tasks", "run_id")
    op.add_column("enrichment_tasks", sa.Column("source_metadata", sa.JSON(), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("checksum", sa.String(128), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("file_type", sa.String(50), nullable=True))
    op.add_column("enrichment_tasks", sa.Column("storage_path", sa.Text(), nullable=True))
    op.alter_column("enrichment_tasks", "document_id", new_column_name="file_id")
