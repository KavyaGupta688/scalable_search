"""
Layer 3 - Vector Database Client
Manages connections and basic operations for Qdrant.
Wraps the qdrant-client logic to isolate vector DB specifics from domain code.
"""

import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from modules.ai_tag_description_generation.app.config import settings


class QdrantManager:
    """Singleton wrapper around QdrantClient."""

    def __init__(self):
        # We initialize synchronously.
        self.client = QdrantClient(
            url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None
        )
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = settings.QDRANT_VECTOR_SIZE

    def ensure_collection(self, *, create_if_missing: bool = False) -> None:
        """Verify the configured collection, optionally creating it.

        Network, authentication, and TLS errors are intentionally propagated.
        They must never be treated as a missing collection in a cloud setup.
        """
        if self.client.collection_exists(self.collection_name):
            info = self.client.get_collection(self.collection_name)
            vectors = info.config.params.vectors
            if (
                vectors.size != self.vector_size
                or str(vectors.distance).lower() != "cosine"
            ):
                raise RuntimeError("Incompatible Qdrant collection schema")
            return
        if not create_if_missing:
            raise RuntimeError(
                f"Qdrant collection '{self.collection_name}' does not exist. "
                "Provision it explicitly or set QDRANT_CREATE_COLLECTION_IF_MISSING=true."
            )
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(
                size=self.vector_size,
                distance=qmodels.Distance.COSINE,
            ),
        )

    def _generate_uuid(self, string_id: str) -> str:
        """Use the same canonical document UUID as Search and the indexer."""
        from modules.shared.integration import point_id

        return point_id(string_id)

    def upsert_embedding(
        self, file_id: str, vector: list[float], metadata_payload: dict
    ) -> None:
        """Insert or update a vector for a file."""
        self.ensure_collection(
            create_if_missing=settings.QDRANT_CREATE_COLLECTION_IF_MISSING
        )
        point_id = self._generate_uuid(file_id)

        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                qmodels.PointStruct(
                    id=point_id, vector=vector, payload=metadata_payload
                )
            ],
        )

    def search_similar(self, vector: list[float], limit: int = 10) -> list:
        """Search for visually/semantically similar items."""
        return self.client.search(
            collection_name=self.collection_name, query_vector=vector, limit=limit
        )


# Singleton instance
qdrant_manager = QdrantManager()

if __name__ == "__main__":
    print(f"QdrantManager initialized targeting {settings.QDRANT_COLLECTION_NAME}")
