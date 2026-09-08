from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from functools import lru_cache
import os

class Settings(BaseSettings):
    APP_NAME: str = "Multimodal Search API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./multimodal_search.db"
    # Connection pool sizing (applied only for PostgreSQL; SQLite ignores these).
    # Keep total (pool_size + max_overflow) * app_replica_count under Postgres max_connections.
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE_SECONDS: int = 1800
    DB_POOL_PRE_PING: bool = True
    # Auto-create tables via SQLAlchemy metadata on startup. Disable in production
    # in favor of a real migration tool (Alembic) once schema changes need history.
    DB_AUTO_CREATE_SCHEMA: bool = True

    # Qdrant Vector DB
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "multimodal_files"
    # Embedded (local file / in-process) Qdrant. Only supported for local dev -
    # it cannot shard, replicate, or run as a cluster. Production must run
    # against a real Qdrant server/cluster (QDRANT_EMBEDDED=False).
    QDRANT_EMBEDDED: bool = True
    QDRANT_STORAGE_PATH: str = "./qdrant_storage"
    QDRANT_PREFER_GRPC: bool = True
    QDRANT_TIMEOUT_SECONDS: float = 10.0
    # Explicit, not inferred from QDRANT_API_KEY being set - the qdrant-client
    # library defaults to assuming HTTPS whenever an API key is present,
    # which breaks a plain local/self-hosted Qdrant that has an API key
    # configured but no TLS termination in front of it (e.g. a bare Docker
    # container). Set True only for Qdrant Cloud or a TLS-terminated server.
    QDRANT_HTTPS: bool = False

    # Qdrant HNSW / collection topology (see capacity-planning doc §1-§4).
    # m=16, ef_construct=128 are Qdrant's recommended defaults for 512-dim
    # CLIP vectors at millions-of-points scale.
    QDRANT_HNSW_M: int = 16
    QDRANT_HNSW_EF_CONSTRUCT: int = 128
    QDRANT_HNSW_EF_SEARCH: int = 128
    QDRANT_FULL_SCAN_THRESHOLD: int = 10000
    QDRANT_ON_DISK_VECTORS: bool = False
    # Shard count is fixed at collection-creation time and cannot be changed
    # without recreating the collection - decide this before first prod ingest.
    QDRANT_SHARD_NUMBER: int = 6
    QDRANT_REPLICATION_FACTOR: int = 2

    # Gate for the bundled sample/demo dataset. Must be explicitly enabled AND
    # not running in production - never an automatic "seed if empty" fallback.
    SEED_SAMPLE_DATA: bool = False

    # Redis Cache
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    # Whether an unreachable Redis is allowed to degrade to an in-process
    # LRU/TTL cache instead of failing the request. This is a per-instance
    # cache (not shared across replicas) - fine for hit-rate, never a source
    # of truth. In production this should normally stay True (search must
    # keep serving even if the cache tier is down) but every fallback event
    # is logged at ERROR so it is alertable; set False to hard-fail instead.
    REDIS_FALLBACK_MEMORY: bool = True

    # Search & RRF Algorithm settings
    RRF_K: int = 60
    RRF_KEYWORD_WEIGHT: float = 0.5
    RRF_VECTOR_WEIGHT: float = 0.5
    DEFAULT_SEARCH_LIMIT: int = 20
    MAX_SEARCH_LIMIT: int = 100

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "clip-ViT-B-32"
    VECTOR_DIMENSION: int = 512

    # Integrations
    DOWNLOAD_AUDITING_SERVICE_URL: str = "http://localhost:8001/api/v1/audit"
    # Must be injected through the environment; never use a shared default secret.
    AUTH_SECRET_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in ("production", "prod")

    @property
    def is_postgres(self) -> bool:
        return self.DATABASE_URL.startswith("postgresql")

@lru_cache()
def get_settings() -> Settings:
    return Settings()
