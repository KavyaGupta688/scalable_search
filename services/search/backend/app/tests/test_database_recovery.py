"""A stale pooled connection must recover without a failed discovery request."""
import pytest
from sqlalchemy import text
from app.db.postgres import engine
from modules.shared.integration import database_engine


@pytest.mark.asyncio
async def test_reconnects_after_own_idle_connection_is_closed():
    # This engine belongs to the test process, not the running Search service.
    # Terminate only the exact backend this test has just checked into its pool.
    await engine.dispose()
    try:
        async with engine.connect() as connection:
            database = await connection.scalar(text("select current_database()"))
            assert database == "smsprsm_integration" or "test" in database
            old_pid = await connection.scalar(text("select pg_backend_pid()"))
        with database_engine("search").connect() as control:
            assert control.execute(text("select current_database()")).scalar_one() == database
            assert control.execute(text("select pg_terminate_backend(:pid)"), {"pid": old_pid}).scalar_one()
        async with engine.connect() as connection:
            assert await connection.scalar(text("select pg_backend_pid()")) != old_pid
            assert await connection.scalar(text("select 1")) == 1
    finally:
        await engine.dispose()
