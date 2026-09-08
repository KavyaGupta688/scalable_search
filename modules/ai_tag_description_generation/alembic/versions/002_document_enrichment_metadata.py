"""Add AI metadata linked to the ingestion-owned documents table.

Revision ID: 002_document_enrichment_metadata
Revises: 001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "002_document_enrichment_metadata"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_enrichment_metadata",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("enrichment_version", sa.String(50), nullable=False),
        sa.Column("metadata_version", sa.String(50), nullable=False, server_default="1.0"),
        sa.Column("generated_tags", postgresql.JSONB()),
        sa.Column("short_description", sa.Text()),
        sa.Column("long_description", sa.Text()),
        sa.Column("search_description", sa.Text()),
        sa.Column("accessibility_description", sa.Text()),
        sa.Column("ocr_text", sa.Text()),
        sa.Column("transcribed_text", sa.Text()),
        sa.Column("native_document_text", sa.Text()),
        sa.Column("quality_labels", postgresql.JSONB()),
        sa.Column("privacy_safety_labels", postgresql.JSONB()),
        sa.Column("restricted_metadata", postgresql.JSONB()),
        sa.Column("confidence_scores", postgresql.JSONB()),
        sa.Column("model_versions", postgresql.JSONB()),
        sa.Column("enrichment_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("file_id", "model_version", "enrichment_version", name="uix_document_enrichment_version"),
    )
    op.create_index("ix_document_enrichment_metadata_file_id", "document_enrichment_metadata", ["file_id"])


def downgrade() -> None:
    op.drop_index("ix_document_enrichment_metadata_file_id", table_name="document_enrichment_metadata")
    op.drop_table("document_enrichment_metadata")
