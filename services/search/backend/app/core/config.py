from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from functools import lru_cache
import os


class Settings(BaseSettings):
    APP_NAME: str = "Multimodal Search API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8002

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./multimodal_search.db"

    # Qdrant Vector DB
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "multimodal_files"
    QDRANT_EMBEDDED: bool = False
    QDRANT_STORAGE_PATH: str = "./qdrant_storage"

    # Redis Cache
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_FALLBACK_MEMORY: bool = False

    # Search & RRF Algorithm settings
    RRF_K: int = 60
    RRF_KEYWORD_WEIGHT: float = 0.5
    RRF_VECTOR_WEIGHT: float = 0.5
    DEFAULT_SEARCH_LIMIT: int = 20
    MAX_SEARCH_LIMIT: int = 100
    # Broad CLIP candidate window; query/document reranking rejects weak matches.
    USE_MULTIMODAL_INDEX: bool = True
    SEMANTIC_CANDIDATE_MIN: float = 0.0
    VISUAL_CANDIDATE_MIN: float = 0.26
    SEMANTIC_ACCEPT_MIN: float = 0.42
    VISUAL_ACCEPT_MIN: float = 0.28
    VECTOR_CANDIDATES: int = 200
    VECTOR_SCORE_MARGIN: float = 0.08
    RELEVANCE_MIN_LOGIT: float = -3.0

    # Ranked results scanned when planning a download of the top N. It also bounds how many
    # files an oversized-file skip can look past.
    DOWNLOAD_PLAN_SCAN: int = 30000

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "clip-ViT-B-32"
    VECTOR_DIMENSION: int = 512

    # Integrations
    DOWNLOAD_AUDITING_SERVICE_URL: str = "http://localhost:8001/api/v1/audit"
    AUTH_SECRET_KEY: str = "multimodal-search-secure-jwt-secret-key-2025"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
