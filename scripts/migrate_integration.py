"""Explicit, repeatable integration schema setup. Run against a disposable DB first."""

import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine, text, inspect

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.shared.integration import database_engine
from modules.shared.delivery import DeliveryBase


def main():
    engine = create_engine(os.environ["DATABASE_URL_SYNC"])
    with engine.begin() as conn:
        for schema in (
            "ingestion",
            "enrichment",
            "search",
            "download",
            "audit",
            "identity",
        ):
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    # Adopt only known legacy-owned tables; never delete or guess foreign ownership.
    owners = {
        "ingestion": [
            "connectors",
            "documents",
            "document_metadata",
            "source_assets",
            "license_entitlements",
            "enumeration_checkpoints",
            "ingestion_runs",
            "ingestion_run_items",
            "retention_events",
            "alembic_version",
        ],
        "enrichment": [
            "enrichment_tasks",
            "document_enrichment_metadata",
            "ai_enrichment_alembic_version",
        ],
        "search": ["datasets", "file_metadata", "search_events"],
        "download": ["forensic_audit_logs", "async_download_jobs"],
        "audit": ["audit_events"],
    }
    with engine.begin() as conn:
        inspector = inspect(conn)
        public = set(inspector.get_table_names(schema="public"))
        for schema, tables in owners.items():
            for table in tables:
                if table in public:
                    if inspector.has_table(table, schema=schema):
                        raise RuntimeError(
                            f"Ambiguous legacy ownership: public.{table} and {schema}.{table}"
                        )
                    conn.execute(
                        text(f'ALTER TABLE public."{table}" SET SCHEMA "{schema}"')
                    )
        # Ingestion enums are also owned by its migration graph.
        for name in ("source_type_enum", "connector_status_enum"):
            exists = conn.execute(
                text(
                    "SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' AND t.typname=:name"
                ),
                {"name": name},
            ).scalar()
            if exists:
                conn.execute(text(f'ALTER TYPE public."{name}" SET SCHEMA ingestion'))
    for schema, directory in (
        ("ingestion", ROOT / "services/ingestion"),
        ("enrichment", ROOT / "modules/ai_tag_description_generation"),
    ):
        env = dict(
            os.environ,
            DATABASE_SCHEMA=schema,
            SOURCE_DOCUMENT_SCHEMA="ingestion",
            PYTHONPATH=os.pathsep.join(
                [str(ROOT), str(ROOT / "services/ingestion/src")]
            ),
        )
        subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(directory / "alembic.ini"),
                "upgrade",
                "head",
            ],
            cwd=directory if schema == "ingestion" else ROOT,
            env=env,
            check=True,
        )
    sys.path.insert(0, str(ROOT / "services/search/backend"))
    os.environ["DATABASE_SCHEMA"] = "search"
    from app.db.postgres import Base as SearchBase
    from app.models import file_metadata, dataset, search_event

    SearchBase.metadata.create_all(database_engine("search"))
    with database_engine("search").begin() as conn:
        for ddl in (
            "published BOOLEAN NOT NULL DEFAULT false",
            "enrichment_status VARCHAR(30) NOT NULL DEFAULT 'pending'",
            "vendor_metadata JSON",
            "ai_metadata_version VARCHAR(200)",
        ):
            conn.execute(
                text("ALTER TABLE file_metadata ADD COLUMN IF NOT EXISTS " + ddl)
            )
        naive = conn.execute(
            text(
                "SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='search' AND data_type='timestamp without time zone' AND table_name IN ('datasets','file_metadata','search_events')"
            )
        ).all()
        for table, column in naive:
            conn.execute(
                text(
                    f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE timestamptz USING "{column}" AT TIME ZONE \'UTC\''
                )
            )
        conn.execute(
            text("ALTER TABLE file_metadata ALTER COLUMN file_size TYPE bigint")
        )
        conn.execute(
            text("ALTER TABLE datasets ALTER COLUMN total_size_bytes TYPE bigint")
        )
    sys.path.insert(0, str(ROOT / "services/download"))
    from integrated import Base as DownloadBase
    from database.models import Base as ForensicBase

    DownloadBase.metadata.create_all(database_engine("download"))
    ForensicBase.metadata.create_all(database_engine("download"))
    from modules.shared.audit import migrate

    migrate()
    for schema in ("search", "download"):
        DeliveryBase.metadata.create_all(database_engine(schema))
    from modules.shared.auth.postgres import migrate as migrate_identity

    migrate_identity()
    for schema in ("identity", "search", "download", "audit"):
        with database_engine(schema).begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS integration_migrations (version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO integration_migrations(version) VALUES (1) ON CONFLICT DO NOTHING"
                )
            )
    from modules.shared.vector_store import provision

    provision(create=True)
    print("Integration migrations and vector collection verified")


if __name__ == "__main__":
    main()
