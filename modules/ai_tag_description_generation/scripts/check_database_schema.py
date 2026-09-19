"""Read-only preflight for ingestion identity and AI-owned tables."""

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy import create_engine, text

from modules.ai_tag_description_generation.app.config import settings


def main() -> None:
    print("Connecting to configured PostgreSQL database...", flush=True)
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True, connect_args={"connect_timeout": 10})
    with engine.connect() as connection:
        state = connection.execute(text("""
            SELECT current_database() AS database_name,
                   current_user AS database_user,
                   to_regclass('public.documents')::text AS documents,
                   to_regclass('public.source_assets')::text AS source_assets,
                   to_regclass('public.document_metadata')::text AS vendor_metadata,
                   to_regclass('public.license_entitlements')::text AS entitlements,
                   to_regclass('public.enrichment_tasks')::text AS enrichment_tasks,
                   to_regclass('public.document_enrichment_metadata')::text AS enrichment_metadata,
                   to_regclass('public.ai_enrichment_alembic_version')::text AS migration_ledger
        """)).mappings().one()
        print(dict(state))

        columns = connection.execute(text("""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND (
                (table_name = 'documents' AND column_name IN
                    ('id', 'checksum_sha256', 'size_bytes', 'mime_type', 'entitlement_id'))
                OR
                (table_name = 'document_enrichment_metadata' AND column_name IN
                    ('document_id', 'source_asset_id', 'run_id', 'model_name', 'model_version'))
              )
            ORDER BY table_name, ordinal_position
        """)).all()
        print("integration_columns", columns)
    engine.dispose()


if __name__ == "__main__":
    main()
