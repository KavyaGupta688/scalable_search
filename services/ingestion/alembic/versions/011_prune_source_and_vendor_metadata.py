"""Prune source/vendor metadata and remove local retention events.

Revision ID: 011
Revises: 010
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Preserve useful search terms before removing the redundant keywords array.
    op.execute(
        """
        UPDATE document_metadata
        SET tags = ARRAY(
            SELECT DISTINCT value
            FROM unnest(
                COALESCE(tags, ARRAY[]::text[])
                || COALESCE(keywords, ARRAY[]::text[])
            ) AS value
            WHERE value <> ''
        )
        """
    )
    op.drop_index("idx_document_metadata_asset_id", table_name="document_metadata")
    op.alter_column("document_metadata", "asset_id", new_column_name="external_asset_id")
    op.create_index(
        "idx_document_metadata_external_asset_id",
        "document_metadata",
        ["external_asset_id"],
    )
    op.add_column(
        "document_metadata",
        sa.Column(
            "additional_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    for column in (
        "filename",
        "keywords",
        "width",
        "height",
        "declared_file_size_bytes",
        "declared_mime_type",
        "camera_make",
        "camera_model",
        "location_name",
        "gps_lat",
        "gps_lon",
        "taken_at",
        "uploaded_at",
        "view_count",
        "download_count",
        "image_type",
        "target_path",
    ):
        op.drop_column("document_metadata", column)

    op.drop_index("idx_source_assets_connector_status", table_name="source_assets")
    op.drop_constraint("ck_source_assets_status", "source_assets", type_="check")
    op.drop_constraint("ck_source_assets_source_type", "source_assets", type_="check")
    op.alter_column("source_assets", "status", new_column_name="availability_status")
    op.create_check_constraint(
        "ck_source_assets_availability_status",
        "source_assets",
        "availability_status IN ('available', 'changed', 'missing', 'inaccessible')",
    )
    op.create_index(
        "idx_source_assets_connector_availability",
        "source_assets",
        ["source_connector_id", "availability_status"],
    )
    op.drop_column("source_assets", "source_type")
    op.drop_column("source_assets", "first_seen_at")

    # Vendor access is not revoked or deleted locally. Current licence state is
    # retained in license_entitlements; audit history belongs to the audit module.
    op.drop_index("idx_retention_events_document_time", table_name="retention_events")
    op.drop_table("retention_events")
    op.execute("DROP FUNCTION IF EXISTS protect_retention_event_update()")


def downgrade() -> None:
    op.create_table(
        "retention_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entitlement_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["entitlement_id"], ["license_entitlements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_retention_events_document_time",
        "retention_events",
        ["document_id", "event_at"],
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

    op.add_column("source_assets", sa.Column("source_type", sa.String(length=16), nullable=True))
    op.execute(
        "UPDATE source_assets AS sa SET source_type = c.source_type::text "
        "FROM connectors AS c WHERE c.id = sa.source_connector_id"
    )
    op.alter_column("source_assets", "source_type", nullable=False)
    op.add_column(
        "source_assets",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.drop_index("idx_source_assets_connector_availability", table_name="source_assets")
    op.drop_constraint("ck_source_assets_availability_status", "source_assets", type_="check")
    op.alter_column("source_assets", "availability_status", new_column_name="status")
    op.create_check_constraint(
        "ck_source_assets_status",
        "source_assets",
        "status IN ('available', 'changed', 'missing', 'inaccessible')",
    )
    op.create_check_constraint(
        "ck_source_assets_source_type",
        "source_assets",
        "source_type IN ('S3', 'NAS_SMB', 'NAS_NFS')",
    )
    op.create_index(
        "idx_source_assets_connector_status",
        "source_assets",
        ["source_connector_id", "status"],
    )

    op.add_column("document_metadata", sa.Column("filename", sa.Text(), nullable=True))
    op.add_column(
        "document_metadata",
        sa.Column("keywords", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )
    op.add_column("document_metadata", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("document_metadata", sa.Column("height", sa.Integer(), nullable=True))
    op.add_column("document_metadata", sa.Column("declared_file_size_bytes", sa.BigInteger(), nullable=True))
    op.add_column("document_metadata", sa.Column("declared_mime_type", sa.Text(), nullable=True))
    op.add_column("document_metadata", sa.Column("camera_make", sa.Text(), nullable=True))
    op.add_column("document_metadata", sa.Column("camera_model", sa.Text(), nullable=True))
    op.add_column("document_metadata", sa.Column("location_name", sa.Text(), nullable=True))
    op.add_column("document_metadata", sa.Column("gps_lat", sa.Numeric(10, 7), nullable=True))
    op.add_column("document_metadata", sa.Column("gps_lon", sa.Numeric(10, 7), nullable=True))
    op.add_column("document_metadata", sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("document_metadata", sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("document_metadata", sa.Column("view_count", sa.BigInteger(), nullable=True))
    op.add_column("document_metadata", sa.Column("download_count", sa.BigInteger(), nullable=True))
    op.add_column("document_metadata", sa.Column("image_type", sa.String(length=32), nullable=True))
    op.add_column("document_metadata", sa.Column("target_path", sa.Text(), nullable=True))
    op.drop_column("document_metadata", "additional_metadata")
    op.drop_index("idx_document_metadata_external_asset_id", table_name="document_metadata")
    op.alter_column("document_metadata", "external_asset_id", new_column_name="asset_id")
    op.create_index("idx_document_metadata_asset_id", "document_metadata", ["asset_id"])
