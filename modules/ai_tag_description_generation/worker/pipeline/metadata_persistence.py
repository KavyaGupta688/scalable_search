# worker/pipeline/metadata_persistence.py
"""
Layer 10 - Metadata Persistence and Embedding.

Upserts generated metadata to PostgreSQL and generates/upserts embeddings to Qdrant.
"""

import logging
from uuid import UUID
from typing import Dict, Any

from app.db import get_sync_session
from app.models import DocumentEnrichmentMetadata
from app.qdrant_client import qdrant_manager
from app.config import settings
from worker.pipeline.model_manager import get_model

logger = logging.getLogger(__name__)


def retry_handler(func):
    """Simple retry decorator for transient failures."""
    def wrapper(*args, **kwargs):
        retries = 3
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if i == retries - 1:
                    raise e
                logger.warning(f"Transient error in {func.__name__}, retrying ({i+1}/{retries}): {e}")
    return wrapper


@retry_handler
def persist_metadata(file_id: str, metadata_record: Dict[str, Any], model_version: str, enrichment_version: str) -> str:
    """Upsert metadata to PostgreSQL."""
    with get_sync_session() as session:
        document_id = UUID(file_id)
        existing = session.query(DocumentEnrichmentMetadata).filter_by(
            file_id=document_id,
            model_version=model_version,
            enrichment_version=enrichment_version
        ).first()

        if existing:
            # Update fields
            for key, value in metadata_record.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            session.commit()
            return existing.id
        else:
            # Insert new
            new_record = DocumentEnrichmentMetadata(
                file_id=document_id,
                model_version=model_version,
                enrichment_version=enrichment_version,
                **metadata_record
            )
            session.add(new_record)
            session.commit()
            return str(new_record.id)


def forward_for_embedding(file_id: str, metadata_record: Dict[str, Any]) -> bool:
    """Generate CLIP embedding and upsert to Qdrant."""
    try:
        tags = metadata_record.get('tags', [])
        short_desc = metadata_record.get('short_description', '')
        search_desc = metadata_record.get('search_description', '')
        
        # Build text representation
        text_parts = []
        if tags:
            text_parts.append(f"Tags: {', '.join(tags)}")
        if short_desc:
            text_parts.append(f"Description: {short_desc}")
        if search_desc:
            text_parts.append(f"Details: {search_desc}")
            
        text_representation = " | ".join(text_parts)
        if not text_representation:
            logger.info(f"No text to embed for {file_id}")
            return False

        # Generate embedding
        clip_model = get_model('clip')
        vector = clip_model.encode_text(text_representation)

        # Build payload
        payload = {
            "file_id": file_id,
            "tags": tags,
            "short_description": short_desc
        }

        # Upsert
        qdrant_manager.upsert_embedding(file_id, vector, payload)
        return True
    except Exception as e:
        logger.error(f"Failed to forward for embedding {file_id}: {e}")
        return False


if __name__ == "__main__":
    pass
