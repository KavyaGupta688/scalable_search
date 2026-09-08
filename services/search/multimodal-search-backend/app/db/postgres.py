from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

if settings.is_production and not settings.is_postgres:
    raise RuntimeError(
        "APP_ENV=production requires a PostgreSQL DATABASE_URL (postgresql+asyncpg://...). "
        "SQLite cannot serve 3,000+ concurrent users or hold a 500TB-scale metadata catalog "
        "(no real connection pooling, no GIN/full-text indexing, single-writer). "
        "Set DATABASE_URL to a PostgreSQL instance before starting in production."
    )

# Connection pool sizing only applies to PostgreSQL - aiosqlite uses its own
# single-connection pool and rejects pool_size/max_overflow kwargs. Keep
# (DB_POOL_SIZE + DB_MAX_OVERFLOW) * app_replica_count under Postgres's
# max_connections, and put PgBouncer in front once replica count grows.
_engine_kwargs = dict(echo=False, future=True)
if settings.is_postgres:
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

# Weighted full-text expression indexed by _ensure_search_indexes() below.
# The search repository's Postgres query path (file_repository.py) MUST
# build its tsquery match/rank expressions against this exact same
# expression so the planner can use the index.
FTS_EXPRESSION_SQL = """
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(category, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(caption, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(content_summary, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'C') ||
    setweight(to_tsvector('english', coalesce(ocr_text, '')), 'D') ||
    setweight(to_tsvector('english', coalesce(transcript, '')), 'D')
"""


async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _create_index_concurrently(conn, index_name: str, create_sql: str) -> None:
    """
    Builds one index CONCURRENTLY, self-healing from a previously interrupted
    build. A CONCURRENTLY build that gets killed midway (app crash, container
    restart) leaves behind an index that exists by name but is marked
    invalid in Postgres's catalog (pg_index.indisvalid = false) - it's never
    used for queries, and a plain CREATE INDEX CONCURRENTLY IF NOT EXISTS
    would then see the name taken and silently do nothing forever. Detect
    that state and drop it first so the build actually retries.
    """
    result = await conn.execute(
        text(
            "SELECT indisvalid FROM pg_index "
            "JOIN pg_class ON pg_class.oid = pg_index.indexrelid "
            "WHERE pg_class.relname = :name"
        ),
        {"name": index_name},
    )
    row = result.first()
    if row is not None and row[0] is False:
        logger.warning(
            f"Found invalid leftover index '{index_name}' from an interrupted "
            f"concurrent build - dropping it so the build can retry."
        )
        await conn.execute(text(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}"))

    await conn.execute(text(create_sql))


async def _ensure_search_indexes(db_engine) -> None:
    """
    Creates the GIN full-text index (title/category/caption/description/
    ocr_text/transcript, weighted) and a pg_trgm index for fuzzy title
    matching. Payload/filter indexing is Qdrant's job (see db/qdrant.py);
    this is Postgres's equivalent for keyword search per the capacity
    doc's §4.5/§7 guidance.

    Built CONCURRENTLY rather than with a plain CREATE INDEX: a plain
    CREATE INDEX takes a lock that blocks all writes to file_metadata for
    the entire build. That's invisible on this app's tiny dev table, but the
    very first time this ever runs against an already-large, already-live
    production table, a blocking build could freeze ingestion for minutes.
    CONCURRENTLY avoids that lock entirely, at the cost of a slower,
    two-pass build - the right trade for a table real users are writing to.

    CONCURRENTLY cannot run inside a transaction block (Postgres rejects
    it), so this uses its own autocommit-mode connection rather than the
    schema-creation transaction in init_db(). It's still cheap to re-run
    (IF NOT EXISTS) on every startup, since there is no migration framework
    in this project yet - after the first real build, every later call is
    just a fast catalog-name check, not a rebuild.
    """
    autocommit_engine = db_engine.execution_options(isolation_level="AUTOCOMMIT")
    try:
        async with autocommit_engine.connect() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

            await _create_index_concurrently(
                conn,
                "ix_file_metadata_fts",
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_file_metadata_fts "
                f"ON file_metadata USING GIN (({FTS_EXPRESSION_SQL}))",
            )
            await _create_index_concurrently(
                conn,
                "ix_file_metadata_title_trgm",
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_file_metadata_title_trgm "
                "ON file_metadata USING GIN (title gin_trgm_ops)",
            )
        logger.info("Verified PostgreSQL full-text (GIN) and trigram indexes on file_metadata.")
    except Exception as e:
        logger.warning(f"Could not create PostgreSQL search indexes: {e}")


async def init_db():
    async with engine.begin() as conn:
        if settings.DB_AUTO_CREATE_SCHEMA:
            await conn.run_sync(Base.metadata.create_all)
    if settings.is_postgres:
        await _ensure_search_indexes(engine)
    logger.info("Database tables verified/created successfully.")
