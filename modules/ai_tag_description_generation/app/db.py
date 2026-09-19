"""
Layer 2 - Database Infrastructure
Provides session management for both synchronous (Celery) and asynchronous (FastAPI/async workers) contexts.
"""

from modules.shared.integration import connection_args, schema_name
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, declarative_base
from modules.ai_tag_description_generation.app.config import settings

# Async engine for non-blocking I/O in API or async worker contexts
async_engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connection_args(
        settings.DATABASE_URL, schema_name("enrichment"), asynchronous=True
    ),
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
)
async_session_factory = async_sessionmaker(
    async_engine, expire_on_commit=False, class_=AsyncSession
)

# Sync engine for blocking operations like legacy Celery tasks
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    connect_args=connection_args(settings.DATABASE_URL_SYNC, schema_name("enrichment")),
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
)
sync_session_factory = sessionmaker(bind=sync_engine, expire_on_commit=False)

Base = declarative_base()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields an async session and ensures it is closed safely."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@contextmanager
def get_sync_session() -> Generator:
    """Yields a sync session. Useful in Celery task execution environments."""
    session = sync_session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def init_db() -> None:
    """Initialize database tables. Should be run on startup or migrations."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


if __name__ == "__main__":
    import asyncio

    asyncio.run(init_db())
    print("Database initialized.")
