from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class DatasetSummary(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    category: str
    file_count: int
    total_size_bytes: int
    thumbnail_url: Optional[str] = None
    view_count: int
    download_count: int
    popularity_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class PopularDatasetsResponse(BaseModel):
    datasets: List[DatasetSummary]
    total: int
    formula_info: str = "Popularity Score = Views_7d + (2 * Downloads_7d) + (0.5 * Previews_7d)"
