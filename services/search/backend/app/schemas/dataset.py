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
    view_count_7d: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PopularDatasetsResponse(BaseModel):
    datasets: List[DatasetSummary]
    total: int
    formula_info: str = "Cumulative recorded views + 2 × recorded downloads"
