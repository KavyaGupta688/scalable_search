from pydantic import BaseModel, Field, model_validator
from typing import Literal, Optional, List, Dict, Any
from datetime import datetime
from app.schemas.filters import SearchFilters, FacetsResponse


class SearchRequest(BaseModel):
    query: str = Field(
        ..., min_length=1, description="Keyword or natural language query string"
    )
    filters: Optional[SearchFilters] = None
    search_mode: Literal["hybrid", "vector", "text"] = Field(
        default="hybrid", description="hybrid, vector, text"
    )
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)
    rrf_k: Optional[int] = Field(default=60, ge=1, le=1000, description="RRF smoothing constant k")
    keyword_weight: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    vector_weight: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode='after')
    def valid_weights(self):
        if self.search_mode == 'hybrid' and self.keyword_weight == 0 and self.vector_weight == 0:
            raise ValueError('At least one search weight must be positive')
        return self



class DownloadPlanRequest(BaseModel):
    """A search plus how many of its top results to download."""

    query: str = Field(..., min_length=1)
    filters: Optional[SearchFilters] = None
    search_mode: Literal["hybrid", "vector", "text"] = "hybrid"
    count: Optional[int] = Field(default=None, ge=0, le=1_000_000, description="Top N results; omit for as many as possible")
    include_ids: bool = Field(default=False, description="Return the selected file ids (needed to start the download)")
    rrf_k: Optional[int] = Field(default=60, ge=1, le=1000)
    keyword_weight: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)
    vector_weight: Optional[float] = Field(default=0.5, ge=0.0, le=1.0)

    @model_validator(mode='after')
    def valid_weights(self):
        if self.search_mode == 'hybrid' and self.keyword_weight == 0 and self.vector_weight == 0:
            raise ValueError('At least one search weight must be positive')
        return self



class DownloadPlanResponse(BaseModel):
    total_matches: int
    requested: Optional[int] = None
    count: int
    available: int
    available_bytes: int
    total_bytes: int
    size_basis: str = "source"
    estimated_parts: int
    excluded_oversized: int
    oversized_in_scan: int
    within_limits: bool
    fit_count: int
    truncated: bool
    limits: Dict[str, int]
    file_ids: Optional[List[str]] = None


class VectorSearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        description="Natural language search query to convert to embedding",
    )
    filters: Optional[SearchFilters] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=10000)


class SimilarSearchRequest(BaseModel):
    file_id: str = Field(..., description="Target file ID to find similar items for")
    filters: Optional[SearchFilters] = None
    limit: int = Field(default=10, ge=1, le=50)


class SearchResultScoreInfo(BaseModel):
    rrf_score: float
    keyword_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    vector_similarity: Optional[float] = None
    visual_similarity: Optional[float] = None
    semantic_similarity: Optional[float] = None
    text_score: Optional[float] = None
    match_sources: List[str] = []


class SearchResultItem(BaseModel):
    file_id: str
    dataset_id: str
    dataset_name: str
    file_name: str
    file_type: str
    title: str
    description: Optional[str] = None
    caption: Optional[str] = None
    content_summary: Optional[str] = None
    ocr_snippet: Optional[str] = None
    transcript_snippet: Optional[str] = None
    tags: List[str] = []
    category: str
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    file_size: int
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    ai_generated: bool = False
    pii_detected: bool = False
    ingested_at: datetime
    score_info: SearchResultScoreInfo
    download_count: int = 0
    file_preview_count: int = 0


class SearchResponse(BaseModel):
    query: str
    search_mode: str
    total: int
    limit: int
    offset: int
    execution_time_ms: float
    results: List[SearchResultItem]
    facets: Optional[FacetsResponse] = None
    # True when a component (vector retrieval, relevance verifier) was unavailable and
    # the results come from the remaining ones; degraded_components names them.
    partial_results: bool = False
    degraded_components: List[str] = []


class SuggestionItem(BaseModel):
    text: str
    type: str  # query, tag, category, dataset
    badge: Optional[str] = None


class SuggestionsResponse(BaseModel):
    query: str
    suggestions: List[SuggestionItem]
    total: int


class TrendingItem(BaseModel):
    query: str
    search_count: int
    category: Optional[str] = None
    trending_score: float


class TrendingResponse(BaseModel):
    time_window: str = "last_24_hours"
    trending: List[TrendingItem]
    generated_at: datetime
