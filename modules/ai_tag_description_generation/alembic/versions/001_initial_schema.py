"""Initial AI-module schema: enrichment task tracking.

Revision ID: 001_initial
Revises: (none)
Create Date: 2026-08-29

The ingestion-owned documents table must already exist in the target cloud
database. Task rows are children of that table and are removed with it.
"""
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    source_schema = os.environ.get("SOURCE_DOCUMENT_SCHEMA", "public")
    source_table = os.environ.get("SOURCE_DOCUMENT_TABLE", "documents")
    source_id_column = os.environ.get("SOURCE_DOCUMENT_ID_COLUMN", "id")
    # --- enrichment_tasks ---
    op.create_table(
        "enrichment_tasks",
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=False),
            sa.ForeignKey(
                f"{source_schema}.{source_table}.{source_id_column}",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("current_stage", sa.String(50), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("stage_results", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("locked_by", sa.String(255), nullable=True),
        sa.Column("lock_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("storage_path", sa.Text()),
        sa.Column("file_type", sa.String(50)),
        sa.Column("checksum", sa.String(128)),
        sa.Column("source_metadata", sa.JSON(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','queue_failed','in_progress','completed','partial','needs_review','failed_terminal')",
            name="ck_enrichment_tasks_status",
        ),
    )

def downgrade() -> None:
    op.drop_table("enrichment_tasks")
