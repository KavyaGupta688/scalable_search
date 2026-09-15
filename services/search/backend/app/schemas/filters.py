from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SearchFilters(BaseModel):
    file_types: Optional[List[str]] = Field(default=None, description="List of file types: image, video, audio, document, csv")
    categories: Optional[List[str]] = Field(default=None, description="List of categories (12 standard categories)")
    dataset_ids: Optional[List[str]] = Field(default=None, description="Filter by specific dataset IDs")
    ai_generated: Optional[bool] = Field(default=None, description="Filter by AI generated vs Real content")
    pii_detected: Optional[bool] = Field(default=None, description="Filter by PII detection status")
    tags: Optional[List[str]] = Field(default=None, description="Must match any of these tags")
    date_from: Optional[datetime] = Field(default=None, description="Ingestion start date filter")
    date_to: Optional[datetime] = Field(default=None, description="Ingestion end date filter")
    min_width: Optional[int] = Field(default=None, description="Minimum image/video width")
    min_duration: Optional[float] = Field(default=None, description="Minimum duration in seconds")
    max_duration: Optional[float] = Field(default=None, description="Maximum duration in seconds")

class FacetCountItem(BaseModel):
    value: str
    count: int

class FacetsResponse(BaseModel):
    file_types: List[FacetCountItem]
    categories: List[FacetCountItem]
    datasets: List[FacetCountItem]
    ai_generated: List[FacetCountItem]
    pii_detected: List[FacetCountItem]
    top_tags: List[FacetCountItem]
    total_matches: int
