"""
Layer 1 - Configuration Management
Centralizes all settings from environment variables.
Using Pydantic for validation ensures the application fails fast if required configurations are missing.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


MODULE_ROOT = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=MODULE_ROOT / ".env", env_file_encoding="utf-8")

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    REDIS_URL: str
    QDRANT_URL: str
    QDRANT_API_KEY: str = ""
    RAM_CHECKPOINT_PATH: str = "./checkpoints/ram_plus_swin_large_14m.pth"
    # MinIO settings. Replace the placeholders in .env before processing
    # remote objects; local file paths continue to work without MinIO.
    MINIO_ENDPOINT: str = ""
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = True
    
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
    
    @property
    def CELERY_BROKER_URL(self) -> str:
        # Reusing the redis URL to minimize infrastructure dependencies.
        return self.REDIS_URL
        
    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        # Same logic as broker.
        return self.REDIS_URL

settings = Settings()

if __name__ == "__main__":
    print(f"Loaded config: enrichment version {settings.ENRICHMENT_VERSION}")
