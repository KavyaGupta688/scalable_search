"""Make licence identity independent of connectors and source paths.

Revision ID: 008
Revises: 007
Create Date: 2026-09-09
"""

from typing import Sequence, Union

from alembic import op


revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_immutable_trigger() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS entitlements_immutable_clock "
        "ON license_entitlements"
    )
    op.execute("DROP FUNCTION IF EXISTS protect_entitlement_clock()")


def _create_immutable_trigger() -> None:
    op.execute(
        """
        CREATE FUNCTION protect_entitlement_clock() RETURNS trigger AS $$
        BEGIN
            IF NEW.license_subject_id IS DISTINCT FROM OLD.license_subject_id
               OR NEW.license_start_at IS DISTINCT FROM OLD.license_start_at
               OR NEW.expires_at IS DISTINCT FROM OLD.expires_at
               OR NEW.policy_code IS DISTINCT FROM OLD.policy_code
               OR NEW.revision IS DISTINCT FROM OLD.revision
               OR NEW.supersedes_entitlement_id IS DISTINCT FROM OLD.supersedes_entitlement_id
               OR NEW.approval_reference IS DISTINCT FROM OLD.approval_reference THEN
                RAISE EXCEPTION 'licence clock and approval fields are immutable; create a renewal revision';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER entitlements_immutable_clock "
        "BEFORE UPDATE ON license_entitlements "
        "FOR EACH ROW EXECUTE FUNCTION protect_entitlement_clock()"
    )


def upgrade() -> None:
    _drop_immutable_trigger()

    # A document supplies the checksum for its directly linked entitlement.
    # Renewal revisions inherit the same identity from the entitlement they
    # supersede. This keeps every historical revision under one content key.
    op.execute(
        """
        WITH RECURSIVE entitlement_subjects(id, subject) AS (
            SELECT e.id, 'sha256:' || lower(d.checksum_sha256)
            FROM license_entitlements AS e
            JOIN documents AS d ON d.entitlement_id = e.id

            UNION

            SELECT child.id, parent.subject
            FROM license_entitlements AS child
            JOIN entitlement_subjects AS parent
              ON child.supersedes_entitlement_id = parent.id
        )
        UPDATE license_entitlements AS entitlement
        SET license_subject_id = subjects.subject
        FROM entitlement_subjects AS subjects
        WHERE entitlement.id = subjects.id
        """
    )

    # Never silently deploy a mixed identity scheme: an unmappable historical
    # entitlement would leave the new-connector loophole open for that asset.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM license_entitlements
                WHERE license_subject_id !~ '^sha256:[0-9a-f]{64}$'
            ) THEN
                RAISE EXCEPTION
                    'revision 008 could not map every entitlement to a document checksum';
            END IF;
        END;
        $$
        """
    )

    _create_immutable_trigger()


def downgrade() -> None:
    _drop_immutable_trigger()

    # Restore the previous connector/path identity for directly linked rows;
    # renewal descendants inherit it from the revision they supersede.
    op.execute(
        """
        WITH RECURSIVE entitlement_subjects(id, subject) AS (
            SELECT e.id, d.source_connector_id::text || ':' || d.source_ref
            FROM license_entitlements AS e
            JOIN documents AS d ON d.entitlement_id = e.id

            UNION

            SELECT child.id, parent.subject
            FROM license_entitlements AS child
            JOIN entitlement_subjects AS parent
              ON child.supersedes_entitlement_id = parent.id
        )
        UPDATE license_entitlements AS entitlement
        SET license_subject_id = subjects.subject
        FROM entitlement_subjects AS subjects
        WHERE entitlement.id = subjects.id
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM license_entitlements
                WHERE license_subject_id ~ '^sha256:[0-9a-f]{64}$'
            ) THEN
                RAISE EXCEPTION
                    'revision 008 downgrade could not restore every connector/path identity';
            END IF;
        END;
        $$
        """
    )

    _create_immutable_trigger()
