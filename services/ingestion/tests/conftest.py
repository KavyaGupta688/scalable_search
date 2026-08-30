from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Mock settings and Base assuming they'll be provided in ingestion module
class DummySettings:
    DATABASE_URL = "postgresql+asyncpg://ingestion:ingestion@localhost:5432/ingestion_test"

class DummyBase:
    pass

@pytest.fixture
def settings():
    return DummySettings()

@pytest_asyncio.fixture
async def db_session(settings):
    # Setup test DB session
    engine = create_async_engine(settings.DATABASE_URL)
    # Using mock metadata
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client(settings, db_session):
    async with AsyncClient(base_url="http://test") as c:
        yield c

@pytest.fixture
def mock_vault():
    class MockVault:
        pass
    return MockVault()

@pytest.fixture
def mock_minio():
    class MockMinio:
        pass
    return MockMinio()

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test-jwt-token"}
