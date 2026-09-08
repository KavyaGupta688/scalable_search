from __future__ import annotations

import httpx
from ingestion.schemas.metadata import TikaMetadata
from ingestion.storage.minio_client import MinIOClient
from ingestion.config import get_settings
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

async def extract_tika_metadata(object_key: str, minio_client: MinIOClient) -> dict:
    settings = get_settings().tika
    try:
        content = await minio_client.get_object_content(object_key)
        
        async with httpx.AsyncClient() as client:
            response = await client.put(f"{settings.server_endpoint}/meta", content=content, timeout=settings.timeout_seconds)
            response.raise_for_status()
            
            tika_data = TikaMetadata(**response.json())
            return tika_data.model_dump(exclude_unset=True)
            
    except Exception as e:
        logger.warning(f"Failed to extract Tika metadata for {object_key}: {e}")
        return {}
