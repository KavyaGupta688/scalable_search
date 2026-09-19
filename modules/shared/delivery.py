"""Transactional, replay-safe delivery records. Tables are created only by migrations."""

from datetime import datetime, timezone
from sqlalchemy import Column, String, JSON, DateTime, Integer, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.dialects.postgresql import insert


class DeliveryBase(DeclarativeBase):
    pass


class Delivery(DeliveryBase):
    __tablename__ = "integration_outbox"
    key = Column(String(200), primary_key=True)
    kind = Column(String(40), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    delivered_at = Column(DateTime(timezone=True))
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text)


def delivery_statement(key, kind, payload):
    return (
        insert(Delivery)
        .values(key=key, kind=kind, payload=payload)
        .on_conflict_do_nothing(index_elements=["key"])
    )


def enqueue(session, key, kind, payload):
    session.execute(delivery_statement(key, kind, payload))


async def enqueue_async(session, key, kind, payload):
    await session.execute(delivery_statement(key, kind, payload))
