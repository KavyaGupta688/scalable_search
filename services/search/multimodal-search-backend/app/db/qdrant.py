from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
import logging
import os
import uuid
from app.core.config import get_settings
from app.core.exceptions import VectorBackendUnavailableException
from app.clients.embedding_client import get_embedding_client

logger = logging.getLogger(__name__)
settings = get_settings()

# Payload fields that the search API actually filters on (see SearchFilters /
# build_qdrant_filter). Only these get a payload index - indexing high-
# cardinality free-text fields wastes RAM/disk for no query benefit, and
# unindexed fields simply fall back to Qdrant's unindexed scan for that clause.
FILTERABLE_PAYLOAD_FIELDS: dict[str, qmodels.PayloadSchemaType] = {
    "file_id": qmodels.PayloadSchemaType.KEYWORD,
    "dataset_id": qmodels.PayloadSchemaType.KEYWORD,
    "file_type": qmodels.PayloadSchemaType.KEYWORD,
    "category": qmodels.PayloadSchemaType.KEYWORD,
    "ai_generated": qmodels.PayloadSchemaType.BOOL,
    "pii_detected": qmodels.PayloadSchemaType.BOOL,
    "nsfw_detected": qmodels.PayloadSchemaType.BOOL,
    "source_batch": qmodels.PayloadSchemaType.KEYWORD,
}

_qdrant_client: QdrantClient | None = None
_qdrant_initialized: bool = False


def _connect_embedded() -> QdrantClient:
    os.makedirs(settings.QDRANT_STORAGE_PATH, exist_ok=True)
    return QdrantClient(path=settings.QDRANT_STORAGE_PATH)


def _connect_server() -> QdrantClient:
    return QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        grpc_port=settings.QDRANT_GRPC_PORT,
        prefer_grpc=settings.QDRANT_PREFER_GRPC,
        api_key=settings.QDRANT_API_KEY,
        # Explicit rather than relying on qdrant-client's default of
        # "assume HTTPS whenever an api_key is set" - that heuristic breaks
        # a self-hosted Qdrant with an API key but no TLS in front of it.
        https=settings.QDRANT_HTTPS,
        timeout=settings.QDRANT_TIMEOUT_SECONDS,
    )


def _build_qdrant_client() -> QdrantClient:
    """
    Connects to Qdrant. In production this NEVER silently degrades to an
    empty embedded/in-memory client on failure - a vector backend that
    quietly falls back to an empty DB returns zero results indistinguishable
    from "no matches", which corrupts search-quality metrics and hides real
    incidents. The embedded/in-memory fallback is only permitted outside
    production (APP_ENV=development), matching Qdrant's own production
    guidance.
    """
    if settings.QDRANT_EMBEDDED:
        if settings.is_production:
            raise RuntimeError(
                "QDRANT_EMBEDDED=True is not supported in production (APP_ENV=production). "
                "Embedded/local-file Qdrant cannot shard, replicate, or run as a cluster. "
                "Point QDRANT_HOST/QDRANT_PORT at a real Qdrant server/cluster instead."
            )
        try:
            return _connect_embedded()
        except Exception as e:
            logger.warning(
                f"Could not lock embedded storage path {settings.QDRANT_STORAGE_PATH} ({e}). "
                f"Falling back to in-memory Qdrant client (development only)."
            )
            return QdrantClient(":memory:")

    try:
        client = _connect_server()
        # Force a round-trip now so connection failures surface here, not on
        # the first search request.
        client.get_collections()
        return client
    except Exception as e:
        if settings.is_production:
            logger.critical(f"VECTOR_BACKEND_UNAVAILABLE: could not connect to Qdrant at "
                             f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}: {e}")
            raise VectorBackendUnavailableException(
                f"cannot reach Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
                details={"host": settings.QDRANT_HOST, "port": settings.QDRANT_PORT},
            ) from e
        logger.warning(
            f"Could not connect to Qdrant server ({e}). Falling back to in-memory "
            f"Qdrant client (development only)."
        )
        return QdrantClient(":memory:")


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client, _qdrant_initialized
    if _qdrant_client is None:
        _qdrant_client = _build_qdrant_client()

    if not _qdrant_initialized:
        init_qdrant()

    return _qdrant_client


def _ensure_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """
    Creates payload indexes for filterable fields. Must run before bulk
    ingestion - Qdrant's filterable-HNSW optimization only applies to graph
    edges built after the payload index exists, so creating indexes post-hoc
    means a partial/full reindex to get the filtering speedup.
    """
    try:
        existing = client.get_collection(collection_name).payload_schema or {}
    except Exception:
        existing = {}

    for field_name, schema_type in FILTERABLE_PAYLOAD_FIELDS.items():
        if field_name in existing:
            continue
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
            logger.info(f"Created Qdrant payload index on '{field_name}' ({schema_type}).")
        except Exception as e:
            logger.warning(f"Could not create payload index on '{field_name}': {e}")


def init_qdrant():
    """
    Ensures the collection exists with production-sized HNSW/sharding config
    and that filterable payload indexes are present. Never auto-seeds sample
    data - an empty production collection means "ingestion hasn't run yet"
    (a legitimate, alertable state), not "fill it with fake data".
    """
    global _qdrant_client, _qdrant_initialized
    if _qdrant_client is None:
        _qdrant_client = _build_qdrant_client()

    client = _qdrant_client
    collection_name = settings.QDRANT_COLLECTION_NAME

    try:
        collections = client.get_collections().collections
        collection_names = [c.name for c in collections]

        if collection_name not in collection_names:
            logger.info(
                f"Creating Qdrant collection '{collection_name}' (dim={settings.VECTOR_DIMENSION}, "
                f"cosine, m={settings.QDRANT_HNSW_M}, ef_construct={settings.QDRANT_HNSW_EF_CONSTRUCT}, "
                f"shards={settings.QDRANT_SHARD_NUMBER}, replication_factor={settings.QDRANT_REPLICATION_FACTOR})."
            )
            create_kwargs = dict(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(
                    size=settings.VECTOR_DIMENSION,
                    distance=qmodels.Distance.COSINE,
                    on_disk=settings.QDRANT_ON_DISK_VECTORS,
                ),
                hnsw_config=qmodels.HnswConfigDiff(
                    m=settings.QDRANT_HNSW_M,
                    ef_construct=settings.QDRANT_HNSW_EF_CONSTRUCT,
                    full_scan_threshold=settings.QDRANT_FULL_SCAN_THRESHOLD,
                ),
            )
            # Shard/replication config only applies to real server-mode
            # collections; the embedded/local client rejects these kwargs.
            if not settings.QDRANT_EMBEDDED:
                create_kwargs["shard_number"] = settings.QDRANT_SHARD_NUMBER
                create_kwargs["replication_factor"] = settings.QDRANT_REPLICATION_FACTOR
            client.create_collection(**create_kwargs)

        _ensure_payload_indexes(client, collection_name)

        if settings.SEED_SAMPLE_DATA and not settings.is_production:
            _seed_sample_data_if_empty(client, collection_name)
        elif settings.SEED_SAMPLE_DATA and settings.is_production:
            logger.error(
                "SEED_SAMPLE_DATA=True is ignored because APP_ENV=production. "
                "Sample/demo data must never be loaded into a production collection."
            )

        _qdrant_initialized = True
    except VectorBackendUnavailableException:
        raise
    except Exception as e:
        logger.warning(f"Error during init_qdrant: {e}")


def _seed_sample_data_if_empty(client: QdrantClient, collection_name: str) -> None:
    """
    Demo-only fallback data. Gated behind the explicit SEED_SAMPLE_DATA flag
    (default False) *and* a non-production environment check - never an
    automatic "seed if empty" trigger on the production code path.
    """
    try:
        info = client.get_collection(collection_name)
        p_count = getattr(info, "points_count", 0) or 0
    except Exception:
        p_count = 0

    if p_count != 0:
        return

    embedder = get_embedding_client()
    sample_docs = [
        ("file_geo_001", "Hyperspectral Mineral Map - Lithium & Rare Earth Basin", "Nature", "image"),
        ("file_sat_001", "Synthetic Aperture Radar (SAR) Polar Ice Velocity Map", "Vehicles", "image"),
        ("file_safe_001", "Heavy Crane Lift Safety Protocol Briefing & Audio Audit", "Technology", "audio"),
        ("file_med_001", "High-Resolution Axial Chest CT Scan with AI Nodule Segmentation", "Medical", "image"),
        ("file_arch_001", "Cable-Stayed Steel Bridge Finite Element Structural Analysis", "Architecture", "document"),
        ("file_anim_001", "Himalayan Snow Leopard Mountain Ridgeline Motion Capture", "Animals", "image"),
    ]
    points = []
    for fid, title, cat, ftype in sample_docs:
        vec = embedder.generate_text_embedding(f"{title} {cat} {ftype}")
        points.append(
            qmodels.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, fid)),
                vector=vec,
                payload={"file_id": fid, "title": title, "category": cat, "file_type": ftype},
            )
        )
    client.upsert(collection_name=collection_name, points=points)
    logger.info(f"Seeded {len(points)} sample vectors into Qdrant collection (SEED_SAMPLE_DATA=True, dev only).")
