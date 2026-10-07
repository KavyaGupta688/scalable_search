from fastapi import Depends
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import logging
from app.core.config import get_settings
from modules.shared.integration import connection_args, schema_name

logger = logging.getLogger(__name__)
settings = get_settings()


def _create_engine(url):
    from sqlalchemy.engine import make_url

    args = connection_args(url, schema_name("search"), asynchronous=True)
    size = settings.DB_STATEMENT_CACHE_SIZE
    if size is not None and url.startswith("postgresql+asyncpg"):
        # PgBouncer in transaction mode hands each transaction a different server
        # connection, so neither asyncpg nor SQLAlchemy may keep prepared statements.
        args["statement_cache_size"] = size
        url = make_url(url).update_query_dict({"prepared_statement_cache_size": str(size)})
    return create_async_engine(
        url,
        connect_args=args,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def _sessionmaker(bind):
    return async_sessionmaker(
        bind=bind,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# Engine creation
engine = _create_engine(settings.DATABASE_URL)
AsyncSessionLocal = _sessionmaker(engine)

# Optional streaming replica for heavy read-only work (keyword ranking, facets). Anything
# that grants access (result rows, licence checks, downloads) stays on the primary.
read_engine = _create_engine(settings.DATABASE_READ_URL) if settings.DATABASE_READ_URL else None
ReadSessionLocal = _sessionmaker(read_engine) if read_engine is not None else None

Base = declarative_base()


async def get_db_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_read_db_session(primary: AsyncSession = Depends(get_db_session)):
    """Replica session when one is configured, otherwise the request's primary session."""
    if ReadSessionLocal is None:
        yield primary
        return
    async with ReadSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created successfully.")
