"""Replace MinIO destination state with zero-copy source assets.

Revision ID: 009
Revises: 008
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_document_identity_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION protect_document_retention_identity() RETURNS trigger AS $$
        BEGIN
            IF NEW.entitlement_id IS DISTINCT FROM OLD.entitlement_id
               OR NEW.checksum_sha256 IS DISTINCT FROM OLD.checksum_sha256 THEN
                RAISE EXCEPTION 'document checksum and entitlement link are immutable';
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
    op.create_table(
        "source_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_connector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("source_version_id", sa.Text(), nullable=True),
        sa.Column("source_last_modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="available"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_type IN ('S3', 'NAS_SMB', 'NAS_NFS')",
            name="ck_source_assets_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('available', 'changed', 'missing', 'inaccessible')",
            name="ck_source_assets_status",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["source_connector_id"], ["connectors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_source_assets_document", "source_assets", ["document_id"])
    op.create_index(
        "uq_source_assets_active_location",
        "source_assets",
        ["source_connector_id", "source_ref"],
        unique=True,
        postgresql_where=sa.text("status = 'available'"),
    )
    op.create_index(
        "idx_source_assets_connector_status",
        "source_assets",
        ["source_connector_id", "status"],
    )

    # Preserve the preferred location currently held on each canonical row.
    op.execute(
        """
        INSERT INTO source_assets (
            id, document_id, source_connector_id, source_type, source_ref,
            size_bytes, status, first_seen_at, last_verified_at
        )
        SELECT
            md5(d.id::text || ':' || d.source_connector_id::text || ':' || d.source_ref)::uuid,
            d.id, d.source_connector_id, c.source_type::text, d.source_ref,
            d.size_bytes, 'available', e.license_start_at, e.license_start_at
        FROM documents AS d
        JOIN connectors AS c ON c.id = d.source_connector_id
        JOIN license_entitlements AS e ON e.id = d.entitlement_id
        """
    )
    # Preserve all historical duplicate locations as first-class source assets.
    op.execute(
        """
        INSERT INTO source_assets (
            id, document_id, source_connector_id, source_type, source_ref,
            size_bytes, status, first_seen_at, last_verified_at
        )
        SELECT DISTINCT ON (dl.source_connector_id, dl.source_ref)
            md5(dl.original_document_id::text || ':' || dl.source_connector_id::text || ':' || dl.source_ref)::uuid,
            dl.original_document_id, dl.source_connector_id, c.source_type::text,
            dl.source_ref, d.size_bytes, 'available', dl.detected_at, dl.detected_at
        FROM duplicate_links AS dl
        JOIN documents AS d ON d.id = dl.original_document_id
        JOIN connectors AS c ON c.id = dl.source_connector_id
        WHERE NOT EXISTS (
            SELECT 1 FROM documents AS preferred
            WHERE preferred.source_connector_id = dl.source_connector_id
              AND preferred.source_ref = dl.source_ref
        )
        ORDER BY dl.source_connector_id, dl.source_ref, dl.detected_at
        """
    )

    op.execute("DROP TRIGGER IF EXISTS documents_immutable_retention ON documents")
    op.execute("DROP FUNCTION IF EXISTS protect_document_retention_identity()")
    op.drop_index("idx_documents_retention_entitlement", table_name="documents")
    op.drop_table("duplicate_links")
    op.drop_column("documents", "storage_path")
    op.drop_column("documents", "bucket_name")
    op.drop_column("documents", "object_version_id")
    op.drop_column("documents", "retention_status")
    op.drop_column("documents", "deleted_at")
    op.drop_column("documents", "last_reconciled_at")
    _create_document_identity_trigger()


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS documents_immutable_retention ON documents")
    op.execute("DROP FUNCTION IF EXISTS protect_document_retention_identity()")

    op.add_column("documents", sa.Column("storage_path", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("bucket_name", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("object_version_id", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("retention_status", sa.String(length=32), nullable=False, server_default="active"),
    )
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE documents
        SET storage_path = source_connector_id::text || '/' || source_ref,
            bucket_name = 'legacy-zero-copy-source'
        """
    )
    op.alter_column("documents", "storage_path", nullable=False)
    op.alter_column("documents", "bucket_name", nullable=False)
    op.create_check_constraint(
        "ck_documents_retention_status",
        "documents",
        "retention_status IN ('active', 'expiry_due', 'deletion_pending', "
        "'deleted_by_reconciler', 'already_absent_at_expiry', "
        "'missing_before_expiry', 'held_past_expiry', 'deletion_failed')",
    )
    op.create_index(
        "idx_documents_retention_entitlement",
        "documents",
        ["retention_status", "entitlement_id"],
    )

    op.create_table(
        "duplicate_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_connector_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["original_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["source_connector_id"], ["connectors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_duplinks_original", "duplicate_links", ["original_document_id"])
    op.create_index("idx_duplinks_source_ref", "duplicate_links", ["source_ref"])
    op.execute(
        """
        INSERT INTO duplicate_links (
            id, original_document_id, source_connector_id, source_ref, detected_at
        )
        SELECT id, document_id, source_connector_id, source_ref, first_seen_at
        FROM source_assets AS sa
        WHERE NOT EXISTS (
            SELECT 1 FROM documents AS d
            WHERE d.id = sa.document_id
              AND d.source_connector_id = sa.source_connector_id
              AND d.source_ref = sa.source_ref
        )
        """
    )
    op.drop_index("idx_source_assets_connector_status", table_name="source_assets")
    op.drop_index("uq_source_assets_active_location", table_name="source_assets")
    op.drop_index("idx_source_assets_document", table_name="source_assets")
    op.drop_table("source_assets")
    _create_document_identity_trigger()
