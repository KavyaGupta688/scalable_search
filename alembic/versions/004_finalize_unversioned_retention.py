"""finalize entitlement-backed unversioned retention schema

Revision ID: 004
Revises: 003
Create Date: 2026-09-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from ingestion.config import get_settings


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    legacy_without_connector = bind.scalar(
        sa.text("SELECT count(*) FROM documents WHERE source_connector_id IS NULL")
    )
    if legacy_without_connector:
        raise RuntimeError(
            "Retention migration requires every existing document to have a source_connector_id; "
            "repair legacy rows before retrying revision 004"
        )

    op.create_table(
        "license_entitlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("license_subject_id", sa.Text(), nullable=False),
        sa.Column(
            "source_connector_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("source_asset_id", sa.Text(), nullable=False),
        sa.Column("license_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "policy_code",
            sa.String(length=64),
            nullable=False,
            server_default="calendar-3y-v1",
        ),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes_entitlement_id", postgresql.UUID(as_uuid=True)),
        sa.Column("approval_reference", sa.Text()),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'renewed', 'revoked')",
            name="ck_license_entitlements_status",
        ),
        sa.CheckConstraint(
            "expires_at >= license_start_at", name="ck_license_entitlements_window"
        ),
        sa.ForeignKeyConstraint(["source_connector_id"], ["connectors.id"]),
        sa.ForeignKeyConstraint(
            ["supersedes_entitlement_id"], ["license_entitlements.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "license_subject_id",
            "revision",
            name="uq_entitlements_subject_revision",
        ),
    )
    op.create_index(
        "idx_entitlements_source_asset",
        "license_entitlements",
        ["source_connector_id", "source_asset_id"],
    )
    op.create_index(
        "idx_entitlements_expiry", "license_entitlements", ["status", "expires_at"]
    )

    op.drop_index("idx_documents_retention_due", table_name="documents")
    op.drop_constraint("ck_documents_retention_window", "documents", type_="check")
    op.drop_constraint("ck_documents_retention_status", "documents", type_="check")

    op.alter_column(
        "documents", "ingested_at", new_column_name="first_successful_ingested_at"
    )
    op.alter_column("documents", "expires_at", new_column_name="effective_expiry_at")
    op.alter_column("documents", "object_deleted_at", new_column_name="deleted_at")
    op.alter_column(
        "documents", "retention_last_checked_at", new_column_name="last_reconciled_at"
    )
    op.alter_column(
        "documents", "retention_last_error", new_column_name="last_error_detail"
    )

    op.add_column("documents", sa.Column("entitlement_id", postgresql.UUID(as_uuid=True)))
    op.add_column("documents", sa.Column("bucket_name", sa.Text()))
    op.add_column(
        "documents", sa.Column("last_uploaded_at", sa.DateTime(timezone=True))
    )
    op.add_column("documents", sa.Column("deletion_method", sa.String(length=64)))
    op.add_column("documents", sa.Column("last_error_code", sa.String(length=64)))
    op.add_column(
        "documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # For legacy rows the connector + canonical source reference is the best
    # available immutable licence subject. Production can later map this to a
    # vendor contract/asset identifier through an approved migration.
    op.execute(
        """
        INSERT INTO license_entitlements (
            id, license_subject_id, source_connector_id, source_asset_id,
            license_start_at, expires_at, policy_code, status, revision, created_at
        )
        SELECT DISTINCT ON (source_connector_id, source_ref)
            md5(source_connector_id::text || ':' || source_ref)::uuid,
            source_connector_id::text || ':' || source_ref,
            source_connector_id,
            source_ref,
            first_successful_ingested_at,
            effective_expiry_at,
            'calendar-3y-v1',
            CASE WHEN effective_expiry_at <= now() THEN 'expired' ELSE 'active' END,
            1,
            first_successful_ingested_at
        FROM documents
        ORDER BY source_connector_id, source_ref, first_successful_ingested_at
        ON CONFLICT (license_subject_id, revision) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE documents
        SET entitlement_id = md5(source_connector_id::text || ':' || source_ref)::uuid
        WHERE entitlement_id IS NULL
        """
    )
    bucket_name = get_settings().minio.bucket
    bind.execute(
        sa.text("UPDATE documents SET bucket_name = :bucket WHERE bucket_name IS NULL"),
        {"bucket": bucket_name},
    )

    # Merge the prototype's status and outcome into one queryable state.
    op.execute(
        """
        UPDATE documents SET retention_status = CASE
            WHEN retention_status = 'deleted' AND lifecycle_outcome = 'deleted_by_reconciler'
                THEN 'deleted_by_reconciler'
            WHEN retention_status = 'deleted' THEN 'already_absent_at_expiry'
            WHEN retention_status = 'missing' THEN 'missing_before_expiry'
            WHEN retention_status IN ('blocked', 'error') THEN 'deletion_failed'
            ELSE 'active'
        END
        """
    )
    op.drop_column("documents", "retention_policy_years")
    op.drop_column("documents", "lifecycle_outcome")

    op.alter_column("documents", "entitlement_id", nullable=False)
    op.alter_column("documents", "bucket_name", nullable=False)
    op.alter_column("documents", "source_connector_id", nullable=False)
    op.create_foreign_key(
        "fk_documents_entitlement",
        "documents",
        "license_entitlements",
        ["entitlement_id"],
        ["id"],
    )
    op.create_index(
        "idx_documents_retention_due",
        "documents",
        ["retention_status", "effective_expiry_at"],
    )
    op.create_check_constraint(
        "ck_documents_retention_status",
        "documents",
        "retention_status IN ('active', 'expiry_due', 'deletion_pending', "
        "'deleted_by_reconciler', 'already_absent_at_expiry', "
        "'missing_before_expiry', 'held_past_expiry', 'deletion_failed')",
    )
    op.create_check_constraint(
        "ck_documents_retention_window",
        "documents",
        "effective_expiry_at >= first_successful_ingested_at",
    )

    op.create_table(
        "retention_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column(
            "event_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Text()),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True)),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text())),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["entitlement_id"], ["license_entitlements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_retention_events_document_time",
        "retention_events",
        ["document_id", "event_at"],
    )

    # Contents expire, but their licensing clock and deletion evidence do not.
    # Database owners can still alter DDL, so production must additionally
    # audit and tightly restrict owner access.
    op.execute(
        """
        CREATE FUNCTION block_retention_audit_delete() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% rows are retention audit records and cannot be deleted', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER documents_no_hard_delete BEFORE DELETE ON documents "
        "FOR EACH ROW EXECUTE FUNCTION block_retention_audit_delete()"
    )
    op.execute(
        """
        CREATE FUNCTION protect_document_retention_identity() RETURNS trigger AS $$
        DECLARE entitlement_expiry timestamptz;
        BEGIN
            SELECT expires_at INTO entitlement_expiry
            FROM license_entitlements WHERE id = NEW.entitlement_id;
            IF entitlement_expiry IS NULL OR NEW.effective_expiry_at IS DISTINCT FROM entitlement_expiry THEN
                RAISE EXCEPTION 'document expiry must equal its entitlement expiry';
            END IF;
            IF TG_OP = 'UPDATE' AND (
               NEW.entitlement_id IS DISTINCT FROM OLD.entitlement_id
               OR NEW.bucket_name IS DISTINCT FROM OLD.bucket_name
               OR NEW.storage_path IS DISTINCT FROM OLD.storage_path
               OR NEW.checksum_sha256 IS DISTINCT FROM OLD.checksum_sha256
               OR NEW.source_connector_id IS DISTINCT FROM OLD.source_connector_id
               OR NEW.source_ref IS DISTINCT FROM OLD.source_ref
               OR NEW.first_successful_ingested_at IS DISTINCT FROM OLD.first_successful_ingested_at
               OR NEW.effective_expiry_at IS DISTINCT FROM OLD.effective_expiry_at) THEN
                RAISE EXCEPTION 'document identity and licence clock are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER documents_immutable_retention BEFORE INSERT OR UPDATE ON documents "
        "FOR EACH ROW EXECUTE FUNCTION protect_document_retention_identity()"
    )
    op.execute(
        "CREATE TRIGGER entitlements_no_hard_delete BEFORE DELETE ON license_entitlements "
        "FOR EACH ROW EXECUTE FUNCTION block_retention_audit_delete()"
    )
    op.execute(
        "CREATE TRIGGER retention_events_append_only_delete BEFORE DELETE ON retention_events "
        "FOR EACH ROW EXECUTE FUNCTION block_retention_audit_delete()"
    )
    op.execute(
        """
        CREATE FUNCTION protect_retention_event_update() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'retention_events is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER retention_events_append_only_update BEFORE UPDATE ON retention_events "
        "FOR EACH ROW EXECUTE FUNCTION protect_retention_event_update()"
    )
    op.execute(
        """
        CREATE FUNCTION protect_entitlement_clock() RETURNS trigger AS $$
        BEGIN
            IF NEW.license_subject_id IS DISTINCT FROM OLD.license_subject_id
               OR NEW.source_connector_id IS DISTINCT FROM OLD.source_connector_id
               OR NEW.source_asset_id IS DISTINCT FROM OLD.source_asset_id
               OR NEW.license_start_at IS DISTINCT FROM OLD.license_start_at
               OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
               OR NEW.policy_code IS DISTINCT FROM OLD.policy_code
               OR NEW.revision IS DISTINCT FROM OLD.revision
               OR NEW.supersedes_entitlement_id IS DISTINCT FROM OLD.supersedes_entitlement_id
               OR NEW.approval_reference IS DISTINCT FROM OLD.approval_reference
               OR NEW.approved_by IS DISTINCT FROM OLD.approved_by THEN
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


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS documents_immutable_retention ON documents"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_document_retention_identity()")
    op.execute(
        "DROP TRIGGER IF EXISTS entitlements_immutable_clock ON license_entitlements"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_entitlement_clock()")
    op.execute(
        "DROP TRIGGER IF EXISTS retention_events_append_only_update ON retention_events"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_retention_event_update()")
    op.execute(
        "DROP TRIGGER IF EXISTS retention_events_append_only_delete ON retention_events"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS entitlements_no_hard_delete ON license_entitlements"
    )
    op.execute("DROP TRIGGER IF EXISTS documents_no_hard_delete ON documents")
    op.execute("DROP FUNCTION IF EXISTS block_retention_audit_delete()")
    op.drop_index("idx_retention_events_document_time", table_name="retention_events")
    op.drop_table("retention_events")
    op.drop_constraint("ck_documents_retention_window", "documents", type_="check")
    op.drop_constraint("ck_documents_retention_status", "documents", type_="check")
    op.drop_index("idx_documents_retention_due", table_name="documents")
    op.drop_constraint("fk_documents_entitlement", "documents", type_="foreignkey")
    op.alter_column("documents", "source_connector_id", nullable=True)

    op.add_column(
        "documents",
        sa.Column(
            "retention_policy_years", sa.Integer(), nullable=False, server_default="3"
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "lifecycle_outcome", sa.String(length=64), nullable=False, server_default="pending"
        ),
    )
    op.execute(
        """
        UPDATE documents SET
            lifecycle_outcome = CASE
                WHEN retention_status = 'deleted_by_reconciler' THEN 'deleted_by_reconciler'
                WHEN retention_status = 'already_absent_at_expiry' THEN 'absent_at_expiry'
                WHEN retention_status = 'missing_before_expiry' THEN 'missing_before_expiry'
                WHEN retention_status = 'deletion_failed' THEN 'deletion_error'
                ELSE 'pending'
            END,
            retention_status = CASE
                WHEN retention_status IN ('deleted_by_reconciler', 'already_absent_at_expiry')
                    THEN 'deleted'
                WHEN retention_status = 'missing_before_expiry' THEN 'missing'
                WHEN retention_status = 'deletion_failed' THEN 'error'
                ELSE 'active'
            END
        """
    )
    op.alter_column(
        "documents", "first_successful_ingested_at", new_column_name="ingested_at"
    )
    op.alter_column("documents", "effective_expiry_at", new_column_name="expires_at")
    op.alter_column("documents", "deleted_at", new_column_name="object_deleted_at")
    op.alter_column(
        "documents", "last_reconciled_at", new_column_name="retention_last_checked_at"
    )
    op.alter_column(
        "documents", "last_error_detail", new_column_name="retention_last_error"
    )
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "last_error_code")
    op.drop_column("documents", "deletion_method")
    op.drop_column("documents", "last_uploaded_at")
    op.drop_column("documents", "bucket_name")
    op.drop_column("documents", "entitlement_id")
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
    )
    op.drop_index("idx_entitlements_expiry", table_name="license_entitlements")
    op.drop_index("idx_entitlements_source_asset", table_name="license_entitlements")
    op.drop_table("license_entitlements")
