# worker/pipeline/metadata_persistence.py
"""
Layer 10 - Metadata Persistence and Embedding.

Upserts generated metadata to PostgreSQL and generates/upserts embeddings to Qdrant.
"""

import logging
from uuid import UUID
from typing import Dict, Any

from modules.ai_tag_description_generation.app.db import get_sync_session
from modules.ai_tag_description_generation.app.models import DocumentEnrichmentMetadata
from modules.ai_tag_description_generation.app.qdrant_client import qdrant_manager
from modules.ai_tag_description_generation.app.config import settings
from modules.ai_tag_description_generation.worker.pipeline.model_manager import get_text_embeddings

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
        tags = metadata_record.get('generated_tags', [])
        short_desc = metadata_record.get('short_description', '')
        search_desc = metadata_record.get('search_description', '')
        
        # Build text representation
        text_parts = []
        if tags:
            labels = [tag.get("tag", "") if isinstance(tag, dict) else str(tag) for tag in tags]
            text_parts.append(f"Tags: {', '.join(label for label in labels if label)}")
        if short_desc:
            text_parts.append(f"Description: {short_desc}")
        if search_desc:
            text_parts.append(f"Details: {search_desc}")
            
        text_representation = " | ".join(text_parts)
        if not text_representation:
            logger.info(f"No text to embed for {file_id}")
            return False

        # Generate embedding
        text_features = get_text_embeddings("metadata_persistence", [text_representation])
        vector = text_features[0].detach().cpu().tolist()

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
