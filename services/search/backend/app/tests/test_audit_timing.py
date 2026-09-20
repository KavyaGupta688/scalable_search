import asyncio
from unittest.mock import AsyncMock, Mock
from app.repositories.analytics_repository import AnalyticsRepository


def test_search_timing_is_carried_in_durable_audit_delivery(monkeypatch):
    from modules.shared import delivery
    db=Mock()
    db.flush=AsyncMock()
    db.commit=AsyncMock()
    db.refresh=AsyncMock()
    enqueue=AsyncMock()
    monkeypatch.setattr(delivery,'enqueue_async',enqueue)
    asyncio.run(AnalyticsRepository(db).log_event('SEARCH','user','user',execution_time_ms=47))
    assert enqueue.call_args.args[3]['execution_time_ms'] == 47
    db.commit.assert_awaited_once()
