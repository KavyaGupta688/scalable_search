"""Initial schema — enrichment_tasks and generated_metadata tables.

Revision ID: 001_initial
Revises: (none)
Create Date: 2026-08-29

This migration creates the two core tables used by the AI enrichment pipeline:
  - enrichment_tasks: tracks file processing jobs through the pipeline
  - generated_metadata: stores AI-generated tags, descriptions, and quality labels
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- enrichment_tasks ---
    op.create_table(
        "enrichment_tasks",
        sa.Column("file_id", sa.String(255), primary_key=True),
        sa.Column("status", sa.String(20), default="queued"),
        sa.Column("current_stage", sa.String(50), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("max_retries", sa.Integer(), default=3),
        sa.Column("stage_results", sa.JSON(), default={}),
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
    )

    # --- generated_metadata ---
    op.create_table(
        "generated_metadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("file_id", sa.String(255), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("enrichment_version", sa.String(50), nullable=False),
        sa.Column("generated_tags", sa.JSON()),
        sa.Column("short_description", sa.Text()),
        sa.Column("long_description", sa.Text()),
        sa.Column("search_description", sa.Text()),
        sa.Column("accessibility_description", sa.Text()),
        sa.Column("extracted_text", sa.JSON()),
        sa.Column("privacy_safety_labels", sa.JSON()),
        sa.Column("quality_labels", sa.JSON()),
        sa.Column("confidence_scores", sa.JSON()),
        sa.Column("raw_model_outputs", sa.JSON()),
        sa.Column("status", sa.String(20), default="pending"),
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
        sa.UniqueConstraint(
            "file_id",
            "model_version",
            "enrichment_version",
            name="uix_file_model_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("generated_metadata")
    op.drop_table("enrichment_tasks")
