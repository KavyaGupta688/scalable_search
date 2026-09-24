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
from modules.ai_tag_description_generation.worker.pipeline.model_manager import (
    encode_text,
)
from modules.ai_tag_description_generation.worker.pipeline.retry_handler import (
    TransientError,
)

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
                    raise TransientError(
                        f"Persistence operation {func.__name__} failed after {retries} attempts: {e}"
                    ) from e
                logger.warning(
                    f"Transient error in {func.__name__}, retrying ({i + 1}/{retries}): {e}"
                )

    return wrapper


@retry_handler
def persist_metadata(
    document_id: str,
    metadata_record: Dict[str, Any],
    model_version: str,
    enrichment_version: str,
) -> str:
    """Upsert metadata to PostgreSQL."""
    metadata_record = dict(metadata_record)
    for uuid_field in ("source_asset_id", "run_id"):
        if metadata_record.get(uuid_field):
            metadata_record[uuid_field] = UUID(str(metadata_record[uuid_field]))
    with get_sync_session() as session:
        normalized_id = UUID(document_id)
        existing = (
            session.query(DocumentEnrichmentMetadata)
            .filter_by(
                document_id=normalized_id,
                model_name="ai_tag_description_generation",
                model_version=model_version,
                enrichment_version=enrichment_version,
            )
            .first()
        )

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
                document_id=normalized_id,
                model_name="ai_tag_description_generation",
                model_version=model_version,
                enrichment_version=enrichment_version,
                **metadata_record,
            )
            session.add(new_record)
            session.commit()
            return str(new_record.id)


def forward_for_embedding(file_id: str, metadata_record: Dict[str, Any], source_path=None, mime_type="") -> bool:
    """Generate CLIP embedding and upsert to Qdrant."""
    try:
        tags = metadata_record.get("generated_tags", [])
        short_desc = metadata_record.get("short_description", "")
        search_desc = metadata_record.get("search_description", "")

        # Build text representation
        text_parts = []
        if tags:
            labels = [
                tag.get("tag", "") if isinstance(tag, dict) else str(tag)
                for tag in tags
            ]
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
        text_features = encode_text([text_representation])
        vector = text_features[0].detach().cpu().tolist()

        # Build payload
        payload = {
            "document_id": file_id,
            "file_id": file_id,
            "published": False,
            "tags": tags,
            "short_description": short_desc,
        }

        # Upsert
        qdrant_manager.upsert_embedding(file_id, vector, payload)
        from modules.shared.semantic_index import collection_name, index_file
        if qdrant_manager.client.collection_exists(collection_name()):
            index_file(file_id, metadata_record, payload, source_path, mime_type)
        return True
    except Exception as e:
        raise TransientError(f"Failed to forward embedding for {file_id}: {e}") from e


if __name__ == "__main__":
    pass
