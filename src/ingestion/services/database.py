"""
Database service: async engine, session factory, and Base class.

Uses SQLAlchemy 2.0+ async patterns with asyncpg.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from ingestion.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def create_engine():
    """Create the async SQLAlchemy engine from settings."""
    settings = get_settings()
    return create_async_engine(
        settings.database.async_url,
        echo=settings.debug,
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_recycle=settings.database.pool_recycle,
        pool_timeout=30,
        pool_pre_ping=True,
        connect_args={"timeout": 10, "command_timeout": 120},
    )


# Module-level engine and session factory.
# Initialized lazily on first access via get_async_session().
_engine = None
_async_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a transactional database session.

    Commits on success, rolls back on exception.
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_raw_session() -> AsyncSession:
    """
    Get a raw session for non-FastAPI contexts (workers, scripts).

    Caller is responsible for commit/rollback/close.
    """
    factory = _get_session_factory()
    return factory()
