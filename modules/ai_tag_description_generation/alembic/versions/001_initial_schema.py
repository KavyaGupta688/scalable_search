"""Initial AI-module schema: enrichment task tracking.

Revision ID: 001_initial
Revises: (none)
Create Date: 2026-08-29

The ingestion-owned documents table must already exist in the target cloud
database. AI output is added by revision 002 with a foreign key to that table.
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

def downgrade() -> None:
    op.drop_table("enrichment_tasks")
