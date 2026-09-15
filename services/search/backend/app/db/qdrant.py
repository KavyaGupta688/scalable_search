from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
import logging
import os
import uuid
from app.core.config import get_settings
from app.clients.embedding_client import get_embedding_client

logger = logging.getLogger(__name__)
settings = get_settings()

_qdrant_client: QdrantClient | None = None
_qdrant_initialized: bool = False

def get_qdrant_client() -> QdrantClient:
    global _qdrant_client, _qdrant_initialized
    if _qdrant_client is None:
        if settings.QDRANT_EMBEDDED:
            try:
                os.makedirs(settings.QDRANT_STORAGE_PATH, exist_ok=True)
                _qdrant_client = QdrantClient(path=settings.QDRANT_STORAGE_PATH)
            except Exception as e:
                logger.warning(f"Could not lock storage path {settings.QDRANT_STORAGE_PATH} ({e}). Falling back to in-memory Qdrant client.")
                _qdrant_client = QdrantClient(":memory:")
        else:
            try:
                _qdrant_client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=10.0
                )
            except Exception:
                _qdrant_client = QdrantClient(":memory:")
        
    if not _qdrant_initialized:
        init_qdrant()
        _qdrant_initialized = True

    return _qdrant_client

def init_qdrant():
    global _qdrant_client, _qdrant_initialized
    if _qdrant_client is None:
        if settings.QDRANT_EMBEDDED:
            try:
                os.makedirs(settings.QDRANT_STORAGE_PATH, exist_ok=True)
                _qdrant_client = QdrantClient(path=settings.QDRANT_STORAGE_PATH)
            except Exception:
                _qdrant_client = QdrantClient(":memory:")
        else:
            try:
                _qdrant_client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=10.0
                )
            except Exception:
                _qdrant_client = QdrantClient(":memory:")

    client = _qdrant_client
    collection_name = settings.QDRANT_COLLECTION_NAME
    
    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        if collection_name not in collection_names:
            logger.info(f"Creating Qdrant collection '{collection_name}' with vector size {settings.VECTOR_DIMENSION} and Cosine distance.")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(
                    size=settings.VECTOR_DIMENSION,
                    distance=qmodels.Distance.COSINE
                )
            )

        # Check if points exist; if empty, seed points
        try:
            info = client.get_collection(collection_name)
            p_count = getattr(info, "points_count", 0) or 0
        except Exception:
            p_count = 0

        if p_count == 0:
            embedder = get_embedding_client()
            sample_docs = [
                ("file_geo_001", "Hyperspectral Mineral Map - Lithium & Rare Earth Basin", "Nature", "image"),
                ("file_sat_001", "Synthetic Aperture Radar (SAR) Polar Ice Velocity Map", "Vehicles", "image"),
                ("file_safe_001", "Heavy Crane Lift Safety Protocol Briefing & Audio Audit", "Technology", "audio"),
                ("file_med_001", "High-Resolution Axial Chest CT Scan with AI Nodule Segmentation", "Medical", "image"),
                ("file_arch_001", "Cable-Stayed Steel Bridge Finite Element Structural Analysis", "Architecture", "document"),
                ("file_anim_001", "Himalayan Snow Leopard Mountain Ridgeline Motion Capture", "Animals", "image")
            ]
            points = []
            for fid, title, cat, ftype in sample_docs:
                vec = embedder.generate_text_embedding(f"{title} {cat} {ftype}")
                points.append(
                    qmodels.PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, fid)),
                        vector=vec,
                        payload={"file_id": fid, "title": title, "category": cat, "file_type": ftype}
                    )
                )
            client.upsert(collection_name=collection_name, points=points)
            logger.info(f"Seeded {len(points)} fallback vectors into Qdrant collection.")
            
        _qdrant_initialized = True
    except Exception as e:
        logger.warning(f"Error during init_qdrant: {e}")
