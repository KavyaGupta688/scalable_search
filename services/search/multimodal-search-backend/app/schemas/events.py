from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class SearchEventCreate(BaseModel):
    event_type: str = Field(..., description="SEARCH, RESULT_CLICK, FILE_PREVIEW, SIMILAR_SEARCH, DATASET_OPEN, DOWNLOAD_REQUEST")
    query: Optional[str] = None
    file_id: Optional[str] = None
    dataset_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None
    result_count: Optional[int] = 0
    meta_info: Optional[Dict[str, Any]] = None

class SearchEventResponse(BaseModel):
    event_id: str
    status: str = "RECORDED"
    timestamp: datetime

class DownloadExportRequest(BaseModel):
    selected_file_ids: List[str] = Field(..., min_length=1, description="List of file IDs selected for download")
    dataset_id: Optional[str] = None
    bundle_metadata_csv: bool = True
    compression_format: str = "zip"
    search_query: Optional[str] = None
    applied_filters: Optional[Dict[str, Any]] = None
    user_notes: Optional[str] = None

class DownloadExportResponse(BaseModel):
    export_task_id: str
    status: str = "SUBMITTED_TO_DOWNLOAD_AUDIT"
    total_files: int
    selected_file_ids: List[str]
    metadata_bundle: str = "metadata.csv"
    audit_event_id: str
    estimated_archive_size_bytes: int
    message: str
