from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

class TechnicalMetadata(BaseModel):
    file_size: int
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    source_batch: Optional[str] = None
    checksum: str

class AIMetadata(BaseModel):
    content_summary: Optional[str] = None
    ocr_text: Optional[str] = None
    transcript: Optional[str] = None
    caption: Optional[str] = None
    pii_detected: bool = False
    nsfw_detected: bool = False
    ai_generated: bool = False
    embedding_model: str
    embedding_version: str
    embedding_status: str

class FileMetadataRead(BaseModel):
    file_id: str
    dataset_id: str
    dataset_name: str
    file_name: str
    file_type: str
    title: str
    description: Optional[str] = None
    tags: List[str] = []
    category: str
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    ingested_at: datetime
    technical: TechnicalMetadata
    ai_enrichment: AIMetadata
    download_count: int = 0
    file_preview_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class FilePreviewResponse(BaseModel):
    file_id: str
    title: str
    file_name: str
    file_type: str
    category: str
    dataset_name: str
    thumbnail_url: Optional[str] = None
    preview_url: Optional[str] = None
    description: Optional[str] = None
    caption: Optional[str] = None
    ocr_text: Optional[str] = None
    transcript: Optional[str] = None
    content_summary: Optional[str] = None
    tags: List[str] = []
    technical: TechnicalMetadata
    ai_enrichment: AIMetadata
    download_count: int
    preview_count: int
