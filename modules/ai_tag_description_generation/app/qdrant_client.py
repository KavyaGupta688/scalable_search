"""
Layer 3 - Vector Database Client
Manages connections and basic operations for Qdrant.
Wraps the qdrant-client logic to isolate vector DB specifics from domain code.
"""
import hashlib
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.config import settings

class QdrantManager:
    """Singleton wrapper around QdrantClient."""
    
    def __init__(self):
        # We initialize synchronously. 
        self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = settings.QDRANT_VECTOR_SIZE

    def ensure_collection(self) -> None:
        """Create the collection if it does not already exist."""
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            # Assumes exception means it doesn't exist, which is standard for qdrant client 
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE
                )
            )

    def _generate_uuid(self, string_id: str) -> str:
        """Qdrant requires UUIDs or integers. We hash the file_id to a valid UUID format."""
        m = hashlib.md5()
        m.update(string_id.encode('utf-8'))
        md5_hex = m.hexdigest()
        return f"{md5_hex[:8]}-{md5_hex[8:12]}-{md5_hex[12:16]}-{md5_hex[16:20]}-{md5_hex[20:32]}"

    def upsert_embedding(self, file_id: str, vector: list[float], metadata_payload: dict) -> None:
        """Insert or update a vector for a file."""
        point_id = self._generate_uuid(file_id)
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=metadata_payload
                )
            ]
        )

    def search_similar(self, vector: list[float], limit: int = 10) -> list:
        """Search for visually/semantically similar items."""
        return self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit
        )

# Singleton instance
qdrant_manager = QdrantManager()

if __name__ == "__main__":
    print(f"QdrantManager initialized targeting {settings.QDRANT_COLLECTION_NAME}")
