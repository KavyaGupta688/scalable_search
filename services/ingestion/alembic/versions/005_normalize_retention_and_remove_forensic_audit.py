"""Normalize retention state; preserve forensic tables owned by Download.

Revision ID: 005
Revises: 004
Create Date: 2026-09-08
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_normalized_identity_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION protect_document_retention_identity() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND (
               NEW.entitlement_id IS DISTINCT FROM OLD.entitlement_id
               OR NEW.bucket_name IS DISTINCT FROM OLD.bucket_name
               OR NEW.storage_path IS DISTINCT FROM OLD.storage_path
               OR NEW.checksum_sha256 IS DISTINCT FROM OLD.checksum_sha256
               OR NEW.source_connector_id IS DISTINCT FROM OLD.source_connector_id
               OR NEW.source_ref IS DISTINCT FROM OLD.source_ref) THEN
                RAISE EXCEPTION 'document identity and entitlement link are immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER documents_immutable_retention BEFORE UPDATE ON documents "
        "FOR EACH ROW EXECUTE FUNCTION protect_document_retention_identity()"
    )


def upgrade() -> None:
    # Foreign forensic/identity tables belong to other modules and remain untouched.

    op.execute("DROP TRIGGER IF EXISTS documents_immutable_retention ON documents")
    op.execute("DROP FUNCTION IF EXISTS protect_document_retention_identity()")
    op.drop_constraint("ck_documents_retention_window", "documents", type_="check")
    op.drop_index("idx_documents_retention_due", table_name="documents")

    op.drop_column("documents", "first_successful_ingested_at")
    op.drop_column("documents", "effective_expiry_at")
    op.drop_column("documents", "last_uploaded_at")
    op.drop_column("documents", "deletion_method")
    op.drop_column("documents", "last_error_code")
    op.drop_column("documents", "last_error_detail")
    op.drop_column("documents", "lifecycle_rule_id")
    op.drop_column("documents", "updated_at")

    op.create_index(
        "idx_documents_retention_entitlement",
        "documents",
        ["retention_status", "entitlement_id"],
    )
    _create_normalized_identity_trigger()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS documents_immutable_retention ON documents")
    op.execute("DROP FUNCTION IF EXISTS protect_document_retention_identity()")
    op.drop_index("idx_documents_retention_entitlement", table_name="documents")

    op.add_column("documents", sa.Column("first_successful_ingested_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("effective_expiry_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("last_uploaded_at", sa.DateTime(timezone=True)))
    op.add_column("documents", sa.Column("deletion_method", sa.String(length=64)))
    op.add_column("documents", sa.Column("last_error_code", sa.String(length=64)))
    op.add_column("documents", sa.Column("last_error_detail", sa.Text()))
    op.add_column("documents", sa.Column("lifecycle_rule_id", sa.Text()))
    op.add_column(
        "documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.execute(
        """
        UPDATE documents AS d
        SET first_successful_ingested_at = e.license_start_at,
            effective_expiry_at = e.expires_at,
            last_uploaded_at = e.license_start_at
        FROM license_entitlements AS e
        WHERE e.id = d.entitlement_id
        """
    )
    op.alter_column("documents", "first_successful_ingested_at", nullable=False)
    op.alter_column("documents", "effective_expiry_at", nullable=False)
    op.create_check_constraint(
        "ck_documents_retention_window",
        "documents",
        "effective_expiry_at >= first_successful_ingested_at",
    )
    op.create_index(
        "idx_documents_retention_due",
        "documents",
        ["retention_status", "effective_expiry_at"],
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

    # forensic_audit_logs belonged to no known module and its original DDL is
    # unavailable, so this migration intentionally does not recreate it.
