from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from datetime import datetime, timezone
import uuid
from app.db.postgres import Base

class SearchEvent(Base):
    __tablename__ = "search_events"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(50), nullable=False, index=True)  # SEARCH, RESULT_CLICK, FILE_PREVIEW, SIMILAR_SEARCH, DATASET_OPEN, DOWNLOAD_REQUEST
    query = Column(String(512), nullable=True, index=True)
    normalized_query = Column(String(512), nullable=True, index=True)
    file_id = Column(String(64), nullable=True, index=True)
    dataset_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    user_role = Column(String(50), default="ANALYST")
    filters = Column(JSON, nullable=True)
    result_count = Column(Integer, default=0)
    meta_info = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
