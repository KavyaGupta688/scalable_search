"""add licensed-content retention audit fields

Revision ID: 003
Revises: 002
Create Date: 2026-09-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "documents",
        sa.Column("retention_policy_years", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column("documents", sa.Column("object_version_id", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("retention_status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column("documents", sa.Column("object_deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("retention_last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("retention_last_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("lifecycle_rule_id", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("lifecycle_outcome", sa.String(length=64), nullable=False, server_default="pending"),
    )

    # Existing records retain their original audit timestamp as the best
    # available ingestion-completion evidence. PostgreSQL calendar arithmetic
    # maps a leap-day anniversary to February 28 in a non-leap target year.
    op.execute(
        "UPDATE documents SET ingested_at = created_at, "
        "expires_at = created_at + INTERVAL '3 years' "
        "WHERE ingested_at IS NULL OR expires_at IS NULL"
    )
    op.alter_column("documents", "ingested_at", nullable=False)
    op.alter_column("documents", "expires_at", nullable=False)
    op.create_check_constraint(
        "ck_documents_retention_status",
        "documents",
        "retention_status IN ('active', 'deleted', 'missing', 'blocked', 'error')",
    )
    op.create_check_constraint(
        "ck_documents_retention_window", "documents", "expires_at >= ingested_at"
    )
    op.create_index(
        "idx_documents_retention_due",
        "documents",
        ["retention_status", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_documents_retention_due", table_name="documents")
    op.drop_constraint("ck_documents_retention_window", "documents", type_="check")
    op.drop_constraint("ck_documents_retention_status", "documents", type_="check")
    op.drop_column("documents", "lifecycle_outcome")
    op.drop_column("documents", "lifecycle_rule_id")
    op.drop_column("documents", "retention_last_error")
    op.drop_column("documents", "retention_last_checked_at")
    op.drop_column("documents", "object_deleted_at")
    op.drop_column("documents", "retention_status")
    op.drop_column("documents", "object_version_id")
    op.drop_column("documents", "retention_policy_years")
    op.drop_column("documents", "expires_at")
    op.drop_column("documents", "ingested_at")
