"""Remove unused identity/audit fields and foreign application tables.

Revision ID: 006
Revises: 005
Create Date: 2026-09-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_entitlement_clock_trigger(*, include_legacy_columns: bool) -> None:
    legacy_checks = ""
    if include_legacy_columns:
        legacy_checks = """
               OR NEW.source_connector_id IS DISTINCT FROM OLD.source_connector_id
               OR NEW.source_asset_id IS DISTINCT FROM OLD.source_asset_id
               OR NEW.approved_by IS DISTINCT FROM OLD.approved_by"""
    op.execute(
        f"""
        CREATE FUNCTION protect_entitlement_clock() RETURNS trigger AS $$
        BEGIN
            IF NEW.license_subject_id IS DISTINCT FROM OLD.license_subject_id
               OR NEW.license_start_at IS DISTINCT FROM OLD.license_start_at
               OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
               OR NEW.policy_code IS DISTINCT FROM OLD.policy_code
               OR NEW.revision IS DISTINCT FROM OLD.revision
               OR NEW.supersedes_entitlement_id IS DISTINCT FROM OLD.supersedes_entitlement_id
               OR NEW.approval_reference IS DISTINCT FROM OLD.approval_reference
               {legacy_checks} THEN
                RAISE EXCEPTION 'licence clock and approval fields are immutable; create a renewal revision';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER entitlements_immutable_clock BEFORE UPDATE ON license_entitlements "
        "FOR EACH ROW EXECUTE FUNCTION protect_entitlement_clock()"
    )


def upgrade() -> None:
    # These tables have no model, API, worker, or migration in this module.
    # No CASCADE: unknown cross-module dependencies must fail visibly.
    op.execute("DROP TABLE IF EXISTS async_download_jobs")
    op.execute("DROP TABLE IF EXISTS refresh_sessions")
    op.execute("DROP TABLE IF EXISTS users")

    op.drop_index("idx_documents_created_at", table_name="documents")
    op.drop_column("documents", "created_by")
    op.drop_column("documents", "created_at")

    op.drop_column("connectors", "created_by")
    op.drop_column("connectors", "created_at")
    op.drop_column("connectors", "last_verified_at")

    # Source location remains on documents. The entitlement keeps only its
    # immutable opaque license_subject_id, avoiding duplicate source columns.
    op.execute(
        "DROP TRIGGER IF EXISTS entitlements_immutable_clock ON license_entitlements"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_entitlement_clock()")
    op.drop_index("idx_entitlements_source_asset", table_name="license_entitlements")
    op.execute(
        "ALTER TABLE license_entitlements DROP CONSTRAINT IF EXISTS "
        "license_entitlements_source_connector_id_fkey"
    )
    op.drop_column("license_entitlements", "source_connector_id")
    op.drop_column("license_entitlements", "source_asset_id")
    op.drop_column("license_entitlements", "approved_by")
    _create_entitlement_clock_trigger(include_legacy_columns=False)

    op.drop_column("retention_events", "actor_id")
    op.drop_column("retention_events", "correlation_id")


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS entitlements_immutable_clock ON license_entitlements"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_entitlement_clock()")

    op.add_column(
        "retention_events", sa.Column("actor_id", sa.Text(), nullable=True)
    )
    op.add_column(
        "retention_events",
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
    )

    op.add_column(
        "license_entitlements",
        sa.Column("source_connector_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "license_entitlements", sa.Column("source_asset_id", sa.Text(), nullable=True)
    )
    op.add_column(
        "license_entitlements",
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute(
        """
        UPDATE license_entitlements AS e
        SET source_connector_id = d.source_connector_id,
            source_asset_id = d.source_ref
        FROM documents AS d
        WHERE d.entitlement_id = e.id
        """
    )
    op.create_foreign_key(
        "license_entitlements_source_connector_id_fkey",
        "license_entitlements",
        "connectors",
        ["source_connector_id"],
        ["id"],
    )
    op.create_index(
        "idx_entitlements_source_asset",
        "license_entitlements",
        ["source_connector_id", "source_asset_id"],
    )
    _create_entitlement_clock_trigger(include_legacy_columns=True)

    op.add_column(
        "connectors",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "connectors",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "connectors",
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE documents AS d
        SET created_at = e.license_start_at
        FROM license_entitlements AS e
        WHERE e.id = d.entitlement_id
        """
    )
    op.alter_column(
        "documents",
        "created_at",
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.create_index("idx_documents_created_at", "documents", ["created_at"])

    # Removed foreign tables had no module-owned DDL, so they are not invented
    # during downgrade.
