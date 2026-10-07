"""Explicit Qdrant provisioning and compatible collection validation.

Collection layout (shards, replication, HNSW, quantisation) is fixed when a collection is
created, so it is configured here from the environment and applied only by the migration
path. Request-time code never creates or reconfigures a collection.
"""

import os
from functools import lru_cache
from qdrant_client import QdrantClient, models


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _env_bool(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in ("1", "true", "yes")


@lru_cache
def client():
    return QdrantClient(
        url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        api_key=os.getenv("QDRANT_API_KEY") or None,
        timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "30")),
        # gRPC has lower per-call overhead; it needs port 6334 reachable from the caller.
        prefer_grpc=_env_bool("QDRANT_PREFER_GRPC"),
        grpc_port=_env_int("QDRANT_GRPC_PORT", 6334),
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
    # Licence status lets a revoked or early-expired licence leave the vector candidate
    # set before the authoritative SQL check (see modules/shared/indexer.py).
    "license_status": models.PayloadSchemaType.KEYWORD,
    # Size and resolution filters, evaluated inside Qdrant once payloads are backfilled.
    "file_size": models.PayloadSchemaType.INTEGER,
    "long_edge": models.PayloadSchemaType.INTEGER,
}


def ensure_payload_indexes(q, name=None, indexes=None):
    """Idempotently index every filterable payload key."""
    for field, schema in (indexes or PAYLOAD_INDEXES).items():
        q.create_payload_index(
            name or collection(), field_name=field, field_schema=schema, wait=True
        )


def resolve(q, name):
    """Physical collection behind `name`, which may be a collection or an alias.

    Collections are switched to new layouts through aliases (scripts/migrate_vector_collection.py),
    so callers must not assume the configured name is a physical collection.
    """
    if q.collection_exists(name):
        return name
    aliases = getattr(q.get_aliases(), "aliases", None)
    if not isinstance(aliases, (list, tuple)):
        return None
    for alias in aliases:
        if alias.alias_name == name:
            return alias.collection_name
    return None


def layout_config():
    """Collection layout applied only when a collection is created.

    Defaults suit one node. For the three-node production cluster set
    QDRANT_REPLICATION_FACTOR=2; shard count cannot change after creation.
    """
    quantization = None
    if os.getenv("QDRANT_QUANTIZATION", "").lower() == "int8":
        quantization = models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8, quantile=0.99, always_ram=True
            )
        )
    return dict(
        shard_number=_env_int("QDRANT_SHARD_NUMBER", 6),
        replication_factor=_env_int("QDRANT_REPLICATION_FACTOR", 1),
        write_consistency_factor=_env_int("QDRANT_WRITE_CONSISTENCY_FACTOR", 1),
        hnsw_config=models.HnswConfigDiff(
            m=_env_int("QDRANT_HNSW_M", 16),
            ef_construct=_env_int("QDRANT_HNSW_EF_CONSTRUCT", 128),
            full_scan_threshold=_env_int("QDRANT_FULL_SCAN_THRESHOLD", 10000),
        ),
        on_disk_payload=_env_bool("QDRANT_ON_DISK_PAYLOAD", True),
        quantization_config=quantization,
    )


def search_params():
    """Per-query HNSW search width; rescoring keeps quantised search exact on the shortlist."""
    rescore = models.QuantizationSearchParams(rescore=True, oversampling=2.0)
    return models.SearchParams(
        hnsw_ef=_env_int("QDRANT_HNSW_EF", 128),
        quantization=rescore if os.getenv("QDRANT_QUANTIZATION", "").lower() == "int8" else None,
    )


def provision(create=False):
    q = client()
    physical = resolve(q, collection())
    if physical is None:
        if not create:
            raise RuntimeError("Qdrant collection has not been provisioned")
        q.create_collection(
            collection(),
            vectors_config=models.VectorParams(
                size=512, distance=models.Distance.COSINE
            ),
            **layout_config(),
        )
        physical = collection()
    vectors = q.get_collection(physical).config.params.vectors
    if vectors.size != 512 or str(vectors.distance).lower() != "cosine":
        raise RuntimeError("Qdrant must contain 512-dimensional cosine CLIP vectors")
    if create:
        # Migration path only; request-time provision() must stay read-only.
        ensure_payload_indexes(q, physical)
    return q
