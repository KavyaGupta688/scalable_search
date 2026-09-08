from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SearchMode(StrEnum):
    TEXT = "text"
    VECTOR = "vector"
    SIMILAR = "similar"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: SearchMode = SearchMode.TEXT
    content_type: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SearchResult(BaseModel):
    file_id: str
    name: str
    content_type: str
    description: str
    tags: list[str]
    score: float = Field(ge=0, le=1)
    created_at: datetime


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    total: int
    results: list[SearchResult]