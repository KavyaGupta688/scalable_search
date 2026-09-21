"""Explicit Qdrant provisioning and compatible collection validation."""

import os
from functools import lru_cache
from qdrant_client import QdrantClient, models


@lru_cache
def client():
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
    )


def collection():
    return os.getenv("QDRANT_COLLECTION_NAME", "multimodal_files")


# Every payload key Search filters on (see app/utils/filters.py and the similar/vector
# services). Without an index Qdrant scans payloads for each filtered query.
PAYLOAD_INDEXES = {
    "file_id": models.PayloadSchemaType.KEYWORD,
    "dataset_id": models.PayloadSchemaType.KEYWORD,
    "file_type": models.PayloadSchemaType.KEYWORD,
    "category": models.PayloadSchemaType.KEYWORD,
    "tags": models.PayloadSchemaType.KEYWORD,
    "published": models.PayloadSchemaType.BOOL,
    "ai_generated": models.PayloadSchemaType.BOOL,
    "pii_detected": models.PayloadSchemaType.BOOL,
    "expires_at": models.PayloadSchemaType.DATETIME,
    "ingested_at": models.PayloadSchemaType.DATETIME,
    "width": models.PayloadSchemaType.INTEGER,
    "duration": models.PayloadSchemaType.FLOAT,
}


def ensure_payload_indexes(q):
    """Idempotently index every filterable payload key."""
    for field, schema in PAYLOAD_INDEXES.items():
        q.create_payload_index(
            collection(), field_name=field, field_schema=schema, wait=True
        )


def provision(create=False):
    q = client()
    if not q.collection_exists(collection()):
        if not create:
            raise RuntimeError("Qdrant collection has not been provisioned")
        q.create_collection(
            collection(),
            vectors_config=models.VectorParams(
                size=512, distance=models.Distance.COSINE
            ),
        )
    vectors = q.get_collection(collection()).config.params.vectors
    if vectors.size != 512 or str(vectors.distance).lower() != "cosine":
        raise RuntimeError("Qdrant must contain 512-dimensional cosine CLIP vectors")
    if create:
        # Migration path only; request-time provision() must stay read-only.
        ensure_payload_indexes(q)
    return q
