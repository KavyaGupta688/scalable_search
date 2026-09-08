from sqlalchemy import Column, String, Integer, DateTime, Text, Float
from datetime import datetime, timezone
from app.db.postgres import Base

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, index=True)
    file_count = Column(Integer, default=0)
    total_size_bytes = Column(Integer, default=0)
    thumbnail_url = Column(String(512), nullable=True)
    
    # Analytics / Popularity
    view_count = Column(Integer, default=0)
    download_count = Column(Integer, default=0)
    search_hit_count = Column(Integer, default=0)
    popularity_score = Column(Float, default=0.0)

    # timezone=True so PostgreSQL stores TIMESTAMPTZ and accepts the
    # timezone-aware datetimes this app writes everywhere (SQLite tolerates
    # naive columns; asyncpg strictly rejects aware-vs-naive mismatches).
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
