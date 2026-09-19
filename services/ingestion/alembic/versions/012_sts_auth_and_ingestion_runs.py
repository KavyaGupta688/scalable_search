"""Add S3 AssumeRole authentication and durable ingestion-run history.

Revision ID: 012
Revises: 011
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("connectors", sa.Column("s3_auth_mode", sa.String(32), nullable=True))
    op.add_column("connectors", sa.Column("s3_role_arn", sa.Text(), nullable=True))
    op.add_column(
        "connectors",
        sa.Column("s3_session_duration_seconds", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        UPDATE connectors
        SET s3_auth_mode = 'static_keys', s3_session_duration_seconds = 3600
        WHERE source_type = 'S3'
        """
    )
    op.create_check_constraint(
        "ck_connectors_s3_auth_mode",
        "connectors",
        "s3_auth_mode IS NULL OR s3_auth_mode IN ('static_keys', 'aws_assume_role')",
    )
    op.create_check_constraint(
        "ck_connectors_s3_session_duration",
        "connectors",
        "s3_session_duration_seconds IS NULL OR "
        "s3_session_duration_seconds BETWEEN 900 AND 43200",
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connector_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("connectors.id"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enumeration_started_at", sa.DateTime(timezone=True)),
        sa.Column("enumeration_completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("enumerated_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("metadata_files_skipped", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("terminal_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("succeeded_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("transient_retry_count", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("bytes_processed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("enumeration_seconds", sa.Float()),
        sa.Column("peak_memory_bytes", sa.BigInteger()),
        sa.Column(
            "enumeration_stats",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_detail", sa.Text()),
        sa.CheckConstraint(
            "status IN ('queued', 'enumerating', 'processing', 'completed', "
            "'completed_with_errors', 'failed')",
            name="ck_ingestion_runs_status",
        ),
    )
    op.create_index(
        "idx_ingestion_runs_connector_triggered",
        "ingestion_runs",
        ["connector_id", "triggered_at"],
    )
    op.create_index("idx_ingestion_runs_status", "ingestion_runs", ["status"])

    op.create_table(
        "ingestion_run_items",
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ingestion_runs.id"),
            primary_key=True,
        ),
        sa.Column("source_ref", sa.Text(), primary_key=True),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_assets.id")),
        sa.Column("outcome", sa.String(32)),
        sa.Column("enumerated_at", sa.DateTime(timezone=True)),
        sa.Column("processing_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bytes_processed", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column(
            "stage_seconds",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_error", sa.Text()),
    )
    op.create_index("idx_ingestion_run_items_document", "ingestion_run_items", ["document_id"])
    op.create_index("idx_ingestion_run_items_source_asset", "ingestion_run_items", ["source_asset_id"])
    op.create_index(
        "idx_ingestion_run_items_outcome", "ingestion_run_items", ["run_id", "outcome"]
    )


def downgrade() -> None:
    op.drop_index("idx_ingestion_run_items_outcome", table_name="ingestion_run_items")
    op.drop_index("idx_ingestion_run_items_source_asset", table_name="ingestion_run_items")
    op.drop_index("idx_ingestion_run_items_document", table_name="ingestion_run_items")
    op.drop_table("ingestion_run_items")
    op.drop_index("idx_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index("idx_ingestion_runs_connector_triggered", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
    op.drop_constraint("ck_connectors_s3_session_duration", "connectors", type_="check")
    op.drop_constraint("ck_connectors_s3_auth_mode", "connectors", type_="check")
    op.drop_column("connectors", "s3_session_duration_seconds")
    op.drop_column("connectors", "s3_role_arn")
    op.drop_column("connectors", "s3_auth_mode")
