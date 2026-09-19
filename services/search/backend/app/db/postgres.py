from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import logging
from app.core.config import get_settings
from modules.shared.integration import connection_args, schema_name

logger = logging.getLogger(__name__)
settings = get_settings()

# Engine creation
engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connection_args(
        settings.DATABASE_URL, schema_name("search"), asynchronous=True
    ),
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created successfully.")
