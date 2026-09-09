from __future__ import annotations

import httpx
from ingestion.schemas.metadata import TikaMetadata
from ingestion.storage.minio_client import MinIOClient
from ingestion.config import get_settings
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Reuse Tika HTTP connections for the lifetime of a worker process."""
    global _http_client
    settings = get_settings().tika
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=settings.timeout_seconds,
            limits=httpx.Limits(
                max_connections=settings.max_connections,
                max_keepalive_connections=settings.max_keepalive_connections,
            ),
        )
    return _http_client

async def extract_tika_metadata(
    object_key: str,
    minio_client: MinIOClient,
    content: bytes | None = None,
) -> dict:
    settings = get_settings().tika
    try:
        client = _get_http_client()
        # Small objects come directly from the bounded upload buffer. Large
        # objects remain streamed from MinIO to keep memory bounded.
        tika_content = content if content is not None else minio_client.open_stream(object_key)
        response = await client.put(
            f"{settings.server_endpoint}/meta",
            content=tika_content,
        )
        response.raise_for_status()

        tika_data = TikaMetadata(**response.json())
        return tika_data.model_dump(exclude_unset=True)
            
    except Exception as e:
        logger.warning(f"Failed to extract Tika metadata for {object_key}: {e}")
        return {}
