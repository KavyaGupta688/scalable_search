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


QUERY_INDEXES = (
    (
        "file_metadata_title_prefix_idx",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS file_metadata_title_prefix_idx "
        "ON file_metadata (lower(title) text_pattern_ops)",
    ),
    (
        "file_metadata_tags_gin_idx",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS file_metadata_tags_gin_idx "
        "ON file_metadata USING gin ((tags::jsonb))",
    ),
    (
        "file_metadata_dataset_published_idx",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS file_metadata_dataset_published_idx "
        "ON file_metadata (dataset_id) WHERE published",
    ),
    (
        # Keyword prefilter (services/search/backend/app/repositories/file_repository.py).
        "file_metadata_search_vector_idx",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS file_metadata_search_vector_idx "
        "ON file_metadata USING gin (search_vector)",
    ),
    (
        # Rows whose vector could not be built still reach the regex match through this.
        "file_metadata_search_vector_missing_idx",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS file_metadata_search_vector_missing_idx "
        "ON file_metadata (file_id) WHERE search_vector IS NULL",
    ),
    (
        "search_events_dataset_views_idx",
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS search_events_dataset_views_idx "
        "ON search_events (event_type, dataset_id, created_at)",
    ),
)


def create_query_indexes(engine, indexes=QUERY_INDEXES):
    """Build indexes without blocking writes or running inside a transaction.

    A cancelled CREATE INDEX CONCURRENTLY can leave an invalid index behind. Remove an
    invalid index on retry instead of letting IF NOT EXISTS mistake it for a usable one.
    """
    with engine.connect() as raw_connection:
        connection = raw_connection.execution_options(isolation_level="AUTOCOMMIT")
        schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        for name, ddl in indexes:
            valid = connection.execute(
                text(
                    "SELECT index_info.indisvalid "
                    "FROM pg_class AS index_relation "
                    "JOIN pg_namespace AS index_schema ON index_schema.oid = index_relation.relnamespace "
                    "JOIN pg_index AS index_info ON index_info.indexrelid = index_relation.oid "
                    "WHERE index_schema.nspname = :schema AND index_relation.relname = :name"
                ),
                {"schema": schema, "name": name},
            ).scalar_one_or_none()
            if valid is True:
                continue
            if valid is False:
                connection.execute(text(f'DROP INDEX CONCURRENTLY IF EXISTS "{name}"'))
            connection.execute(text(ddl))


# The searchable text of a row, in the same field order Search's keyword match uses.
SEARCH_TEXT_SQL = (
    "concat_ws(' ', {r}title, {r}description, {r}file_name, {r}category, {r}content_summary, "
    "{r}ocr_text, {r}transcript, {r}caption, {r}tags::text)"
)

# Every non-alphanumeric run becomes a space before parsing, so each lexeme is exactly a
# maximal [[:alnum:]] run: the same word boundary the regex keyword match uses. That keeps
# the full-text match a superset of the regex match. A text too large for a tsvector yields
# NULL instead of failing the write; NULL rows are always passed on to the regex match.
SEARCH_VECTOR_DDL = (
    """CREATE OR REPLACE FUNCTION search_fts_vector(document text) RETURNS tsvector
    LANGUAGE plpgsql IMMUTABLE SET search_path FROM CURRENT AS $$
    BEGIN
        RETURN strip(to_tsvector('simple',
            regexp_replace(lower(coalesce(document, '')), '[^[:alnum:]]+', ' ', 'g')));
    EXCEPTION WHEN others THEN
        RETURN NULL;
    END $$""",
    """CREATE OR REPLACE FUNCTION file_metadata_search_vector_refresh() RETURNS trigger
    LANGUAGE plpgsql SET search_path FROM CURRENT AS $$
    BEGIN
        NEW.search_vector := search_fts_vector("""
    + SEARCH_TEXT_SQL.format(r="NEW.")
    + """);
        RETURN NEW;
    END $$""",
    "DROP TRIGGER IF EXISTS file_metadata_search_vector_trigger ON file_metadata",
    """CREATE TRIGGER file_metadata_search_vector_trigger
    BEFORE INSERT OR UPDATE OF title, description, file_name, category, content_summary,
        ocr_text, transcript, caption, tags
    ON file_metadata FOR EACH ROW EXECUTE FUNCTION file_metadata_search_vector_refresh()""",
)


# Must equal SEARCH_DOCUMENT_SQL in services/search/backend/app/repositories/file_repository.py.
SEARCH_DOCUMENT_SQL = (
    "coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || "
    "coalesce(file_name, '') || ' ' || coalesce(category, '') || ' ' || "
    "coalesce(content_summary, '') || ' ' || coalesce(ocr_text, '') || ' ' || "
    "coalesce(transcript, '') || ' ' || coalesce(caption, '') || ' ' || "
    "coalesce(CAST(tags AS VARCHAR), '')"
)
TRIGRAM_INDEX = (
    "file_metadata_search_text_trgm_idx",
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS file_metadata_search_text_trgm_idx "
    "ON file_metadata USING gin ((" + SEARCH_DOCUMENT_SQL + ") gin_trgm_ops)",
)


def create_trigram_index(engine):
    """Speeds up keyword search in scripts the full-text vector skips (e.g. CJK, accents).

    Optional: it needs the pg_trgm extension and roughly doubles the keyword-text storage.
    Set SEARCH_TRIGRAM_INDEX=false to skip it. Search detects it at startup.
    """
    if os.getenv("SEARCH_TRIGRAM_INDEX", "true").strip().lower() not in ("1", "true", "yes"):
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    except Exception as exc:
        print(f"Skipping trigram index: pg_trgm is unavailable ({type(exc).__name__})")
        return
    create_query_indexes(engine, indexes=(TRIGRAM_INDEX,))


def backfill_search_vectors(engine, batch=5000):
    """Fill search_vector for existing rows in short keyset-paged transactions."""
    last = ""
    while True:
        with engine.begin() as conn:
            ids = list(
                conn.execute(
                    text(
                        "SELECT file_id FROM file_metadata WHERE file_id > :last "
                        "AND search_vector IS NULL ORDER BY file_id LIMIT :batch"
                    ),
                    {"last": last, "batch": batch},
                ).scalars()
            )
            if not ids:
                return
            conn.execute(
                text(
                    "UPDATE file_metadata SET search_vector = search_fts_vector("
                    + SEARCH_TEXT_SQL.format(r="")
                    + ") WHERE file_id = ANY(:ids)"
                ),
                {"ids": ids},
            )
        last = ids[-1]


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
        conn.execute(
            text("ALTER TABLE file_metadata ADD COLUMN IF NOT EXISTS search_vector tsvector")
        )
        for ddl in SEARCH_VECTOR_DDL:
            conn.execute(text(ddl))
    backfill_search_vectors(database_engine("search"))
    # Build query-path indexes concurrently after the schema transaction commits.
    create_query_indexes(database_engine("search"))
    create_trigram_index(database_engine("search"))
    sys.path.insert(0, str(ROOT / "services/download"))
    from integrated import Base as DownloadBase
    from database.models import Base as ForensicBase

    DownloadBase.metadata.create_all(database_engine("download"))
    ForensicBase.metadata.create_all(database_engine("download"))
    from integration_migrations import upgrade as upgrade_download
    upgrade_download(database_engine("download"))
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
    # Search filters the semantic collection with the same payload keys; index them too.
    from modules.shared import semantic_index
    from modules.shared.vector_store import client, ensure_payload_indexes, resolve

    physical = resolve(client(), semantic_index.collection_name())
    if physical is not None:
        ensure_payload_indexes(client(), physical, semantic_index.payload_indexes())
    print("Integration migrations and vector collection verified")


if __name__ == "__main__":
    main()
