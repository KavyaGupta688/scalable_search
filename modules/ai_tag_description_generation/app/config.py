"""
Layer 1 - Configuration Management
Centralizes all settings from environment variables.
Using Pydantic for validation ensures the application fails fast if required configurations are missing.
"""
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


MODULE_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=MODULE_ROOT / ".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    # REDIS_URL remains the backward-compatible fallback. Production can
    # separate queue traffic, short-lived results, and application events.
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    EVENT_REDIS_URL: str = ""
    CELERY_VISIBILITY_TIMEOUT: int = 7200
    CELERY_RESULT_EXPIRES: int = 3600
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    # Keep automatic collection creation off for cloud deployments. Provision
    # collections deliberately through the connectivity script or IaC.
    QDRANT_CREATE_COLLECTION_IF_MISSING: bool = False
    RAM_CHECKPOINT_PATH: str = "./checkpoints/ram_plus_swin_large_14m.pth"
    YOLO_MODEL_NAME: str = "yolov8s.pt"
    # MinIO settings. Replace the placeholders in .env before processing
    # remote objects; local file paths continue to work without MinIO.
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = True

    # Ingestion-owned source table. This module only reads it. Override these
    # placeholders to match the cloud PostgreSQL schema.
    SOURCE_DOCUMENT_SCHEMA: str = "public"
    SOURCE_DOCUMENT_TABLE: str = "documents"
    SOURCE_DOCUMENT_ID_COLUMN: str = "id"
    SOURCE_STORAGE_PATH_COLUMN: str = "storage_path"
    SOURCE_FILE_TYPE_COLUMN: str = "file_type"
    SOURCE_CHECKSUM_COLUMN: str = "checksum"
    SOURCE_METADATA_COLUMN: str = "source_metadata"

    # Enrichment specifics
    ENRICHMENT_VERSION: str = "1.0.0"
    QDRANT_COLLECTION_NAME: str = "file_embeddings"
    QDRANT_VECTOR_SIZE: int = 512
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_BASE: float = 2.0
    CONFIDENCE_THRESHOLD_COMPLETED: float = 0.7
    CONFIDENCE_THRESHOLD_REVIEW: float = 0.4
    PII_SENSITIVITY: str = "high"
    NSFW_THRESHOLD: float = 0.3

    @field_validator("RAM_CHECKPOINT_PATH", mode="before")
    @classmethod
    def resolve_ram_checkpoint_path(cls, value: str) -> str:
        """Resolve relative checkpoint paths from this module, not the shell CWD."""
        path = Path(value)
        return str(path if path.is_absolute() else MODULE_ROOT / path)

    @model_validator(mode="after")
    def apply_redis_fallbacks(self):
        """Support one legacy URL while allowing production separation."""
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        if not self.EVENT_REDIS_URL:
            self.EVENT_REDIS_URL = self.REDIS_URL
        return self

settings = Settings()

if __name__ == "__main__":
    print(f"Loaded config: enrichment version {settings.ENRICHMENT_VERSION}")
