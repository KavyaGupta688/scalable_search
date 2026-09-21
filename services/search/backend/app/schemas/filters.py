from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
from datetime import datetime

from app.utils.resolution import RESOLUTION_IDS
from app.utils.size_buckets import SIZE_BUCKET_IDS

class SearchFilters(BaseModel):
    file_types: Optional[List[str]] = Field(default=None, description="List of file types: image, video, audio, document, csv")
    categories: Optional[List[str]] = Field(default=None, description="List of categories (12 standard categories)")
    dataset_ids: Optional[List[str]] = Field(default=None, description="Filter by specific dataset IDs")
    ai_generated: Optional[bool] = Field(default=None, description="Filter by AI generated vs Real content")
    pii_detected: Optional[bool] = Field(default=None, description="Filter by PII detection status")
    tags: Optional[List[str]] = Field(default=None, description="Must match any of these tags")
    date_from: Optional[datetime] = Field(default=None, description="Ingestion start date filter")
    date_to: Optional[datetime] = Field(default=None, description="Ingestion end date filter")
    resolutions: Optional[List[str]] = Field(default=None, description="Photo/video resolution tiers: 4k, 2k, fhd, hd, sd, unknown (long edge in pixels)")
    size_buckets: Optional[List[str]] = Field(default=None, description="File size buckets: lt100k, 100k-1m, 1m-10m, 10m-100m, 100m-1g, gte1g")
    min_size: Optional[int] = Field(default=None, ge=0, description="Minimum file size in bytes")
    max_size: Optional[int] = Field(default=None, ge=0, description="Maximum file size in bytes")
    min_width: Optional[int] = Field(default=None, description="Minimum image/video width")
    min_duration: Optional[float] = Field(default=None, description="Minimum duration in seconds")
    max_duration: Optional[float] = Field(default=None, description="Maximum duration in seconds")

    @field_validator("size_buckets")
    @classmethod
    def _known_size_buckets(cls, value):
        if value is None:
            return value
        buckets = [str(v).lower() for v in value]
        unknown = [v for v in buckets if v not in SIZE_BUCKET_IDS]
        if unknown:
            raise ValueError(f"Unknown size bucket(s) {unknown}; use {list(SIZE_BUCKET_IDS)}")
        return buckets or None

    @model_validator(mode="after")
    def _size_range_is_ordered(self):
        if self.min_size is not None and self.max_size is not None and self.min_size > self.max_size:
            raise ValueError("min_size cannot be larger than max_size")
        return self

    @field_validator("resolutions")
    @classmethod
    def _known_resolutions(cls, value):
        if value is None:
            return value
        tiers = [str(v).lower() for v in value]
        unknown = [v for v in tiers if v not in RESOLUTION_IDS]
        if unknown:
            raise ValueError(f"Unknown resolution tier(s) {unknown}; use {list(RESOLUTION_IDS)}")
        return tiers or None


class FacetCountItem(BaseModel):
    value: str
    count: int
    label: Optional[str] = None

class FacetsResponse(BaseModel):
    file_types: List[FacetCountItem]
    categories: List[FacetCountItem]
    datasets: List[FacetCountItem]
    ai_generated: List[FacetCountItem]
    pii_detected: List[FacetCountItem]
    top_tags: List[FacetCountItem]
    resolutions: List[FacetCountItem] = []
    sizes: List[FacetCountItem] = []
    total_matches: int
