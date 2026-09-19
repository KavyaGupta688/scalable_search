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
    return q
