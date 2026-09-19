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
    model_config = SettingsConfigDict(
        env_file=MODULE_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    TASK_LOCK_TTL_SECONDS: int = 7200
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    # Keep automatic collection creation off for cloud deployments. Provision
    # collections deliberately through the connectivity script or IaC.
    QDRANT_CREATE_COLLECTION_IF_MISSING: bool = False
    RAM_CHECKPOINT_PATH: str = "./checkpoints/ram_plus_swin_large_14m.pth"
    YOLO_MODEL_NAME: str = "yolov8s.pt"
    # Ingestion remains the only component allowed to resolve vendor S3/NAS
    # credentials. AI obtains short-lived or streamed bytes through its API.
    INGESTION_API_BASE_URL: str = "http://ingestion-api:8000"
    INGESTION_API_TOKEN: str = ""
    INGESTION_REQUEST_TIMEOUT_SECONDS: float = 30.0
    INGESTION_DOWNLOAD_TIMEOUT_SECONDS: float = 1800.0
    INGESTION_CONTENT_PATH_TEMPLATE: str = "/documents/{document_id}/content"
    MAX_SOURCE_BYTES: int = 5 * 1024 * 1024 * 1024

    # Kafka is the authoritative ingestion trigger. Celery remains the local
    # execution queue used by the API/manual retry path.
    KAFKA_BOOTSTRAP_SERVERS: str = "kafka:29092"
    KAFKA_AI_TOPIC: str = "ai-processing-events"
    KAFKA_AI_DLQ_TOPIC: str = "ai-processing-events-dlq"
    KAFKA_AI_GROUP_ID: str = "ai-tag-generation"
    KAFKA_SECURITY_PROTOCOL: str = "PLAINTEXT"
    KAFKA_SASL_MECHANISM: str = ""
    KAFKA_SASL_USERNAME: str = ""
    KAFKA_SASL_PASSWORD: str = ""
    KAFKA_MAX_POLL_INTERVAL_MS: int = 7_200_000

    # Ingestion-owned canonical document table. Used only for foreign keys;
    # document/source reads go through the ingestion API.
    SOURCE_DOCUMENT_SCHEMA: str = "public"
    SOURCE_DOCUMENT_TABLE: str = "documents"
    SOURCE_DOCUMENT_ID_COLUMN: str = "id"

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
    AI_GENERATED_THRESHOLD: float = 0.8
    TOXICITY_THRESHOLD: float = 0.8

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
