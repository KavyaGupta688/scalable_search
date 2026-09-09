"""
Application configuration via Pydantic Settings.

All configuration is environment-variable driven. No hardcoded secrets anywhere.
Group settings by concern for clarity.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal, Set

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compose injects these variables into containers, but global Alembic runs on
# the Windows host.  Allow both working directories used by this project:
# repository root and deploy/docker.  Environment variables still take
# precedence over values read from these files.
PROJECT_ENV_FILES = (".env", "deploy/docker/.env")


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=PROJECT_ENV_FILES,
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 5432
    name: str = "ingestion"
    user: str = "ingestion"
    password: str = ""  # Must be set via env var or Vault
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 1800

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class MinIOSettings(BaseSettings):
    """MinIO (S3-compatible) destination storage settings."""

    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint_url: str = "http://localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "ingestion-data"
    region: str = "us-east-1"
    secure: bool = False


class KafkaSettings(BaseSettings):
    """Apache Kafka settings for job queue and event bus."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    bootstrap_servers: str = "localhost:9092"
    ingestion_topic: str = "ingestion-jobs"
    dead_letter_topic: str = "ingestion-dead-letter"
    ai_processing_topic: str = "ai-processing-events"
    consumer_group: str = "ingestion-workers"
    # Producer settings
    producer_acks: str = "all"
    producer_enable_idempotence: bool = True
    # Consumer settings
    consumer_auto_offset_reset: str = "earliest"
    consumer_max_poll_interval_ms: int = 300000
    consumer_session_timeout_ms: int = 45000


class VaultSettings(BaseSettings):
    """HashiCorp Vault settings for secrets management."""

    model_config = SettingsConfigDict(env_prefix="VAULT_")

    url: str = "http://localhost:8200"
    token: str = ""  # For dev mode; production uses AppRole
    role_id: str = ""
    secret_id: str = ""
    mount_point: str = "secret"
    auth_mount_point: str = "approle"
    connector_secret_prefix: str = "connectors"
    # Auth method: "token" for dev, "approle" for production
    auth_method: str = "token"


class TikaSettings(BaseSettings):
    """Apache Tika server settings for metadata extraction."""

    model_config = SettingsConfigDict(env_prefix="TIKA_")

    server_endpoint: str = "http://localhost:9998"
    timeout_seconds: int = 30
    max_retries: int = 3
    max_connections: int = 32
    max_keepalive_connections: int = 16


class RetentionSettings(BaseSettings):
    """Licensed-content retention and MinIO lifecycle enforcement settings."""

    model_config = SettingsConfigDict(env_prefix="RETENTION_")

    # Enforcement is opt-in so the migration and dry-run audit can be rolled
    # out before any object-deletion capability is enabled.
    enabled: bool = False
    dry_run: bool = True
    # Option A fails closed if a bucket was ever versioned. Suspended buckets
    # still contain historical versions and are therefore not unversioned.
    expected_bucket_versioning: Literal["Unversioned", "Enabled", "Any"] = "Unversioned"
    write_object_tags: bool = False
    policy_years: int = Field(3, ge=1, le=100)
    object_prefix: str = ""
    lifecycle_rule_id: str = "ingestion-retention-v1"
    # Calendar-year expiry is exact in PostgreSQL/reconciliation.  Lifecycle
    # is a whole-day fail-safe and is deliberately later than any 3-year
    # calendar interval so it cannot remove licensed content early.
    lifecycle_expiration_days: int = Field(1097, ge=1)
    noncurrent_expiration_days: int = Field(1097, ge=1)
    incomplete_multipart_days: int = Field(7, ge=1)
    reconciliation_interval_seconds: int = Field(900, ge=10)
    reconciliation_batch_size: int = Field(500, ge=1, le=10000)
    metrics_port: int = Field(9200, ge=0, le=65535)

    @model_validator(mode="after")
    def lifecycle_must_not_precede_calendar_expiry(self):
        # Maximum leap days in an N-year span, plus one day because the
        # object's Last-Modified timestamp can precede successful ingestion.
        safe_minimum = self.policy_years * 365 + ((self.policy_years + 3) // 4) + 1
        if self.lifecycle_expiration_days < safe_minimum:
            raise ValueError(
                "lifecycle_expiration_days could delete content before its calendar expiry; "
                f"use at least {safe_minimum} days"
            )
        if self.noncurrent_expiration_days < safe_minimum:
            raise ValueError(
                "noncurrent_expiration_days could delete a retained version before its "
                f"calendar expiry; use at least {safe_minimum} days"
            )
        return self


class JWTSettings(BaseSettings):
    """JWT authentication settings."""

    model_config = SettingsConfigDict(env_prefix="JWT_")

    secret_key: str = "CHANGE-ME-IN-PRODUCTION"  # Must be overridden via env
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    # Dev-only token issuance endpoint. MUST be False in production.
    dev_token_enabled: bool = False


class LoggingSettings(BaseSettings):
    """Structured JSON logging settings."""

    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = "INFO"
    service_name: str = "data-ingestion"
    logstash_host: str = ""
    logstash_port: int = 5044
    logstash_transport: str = "tcp"  # "tcp" or "udp"


class WorkerSettings(BaseSettings):
    """Ingestion worker configuration."""

    model_config = SettingsConfigDict(env_prefix="WORKER_")

    chunk_size_bytes: int = 8 * 1024 * 1024  # 8 MB
    # Small objects avoid multipart setup/completion and a second MinIO read.
    # Memory remains bounded by this threshold per worker process.
    single_put_max_bytes: int = 16 * 1024 * 1024
    # Circuit breaker
    circuit_breaker_fail_max: int = 5
    circuit_breaker_reset_timeout_seconds: int = 60
    # Retry
    retry_max_attempts: int = 5
    retry_base_wait_seconds: float = 1.0
    retry_max_wait_seconds: float = 60.0
    # Enumeration checkpointing interval (pages)
    checkpoint_interval_pages: int = 10
    # Reconciliation periodic interval (seconds); 0 = disabled
    reconciliation_interval_seconds: int = 3600
    # Prometheus endpoint for the worker process. Set to 0 to disable.
    metrics_port: int = 9100


# ─── MIME Type Allowlist ─────────────────────────────────────────────
# Configurable via ALLOWED_MIME_TYPES env var (comma-separated).
# Defaults to the spec's list.
DEFAULT_ALLOWED_MIME_TYPES: Set[str] = {
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # Documents
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
    "text/plain",
    "text/csv",
    # Audio
    "audio/mpeg",       # MP3
    "audio/wav",
    "audio/x-wav",
    # Video
    "video/mp4",
    "video/x-msvideo",  # AVI
    "video/quicktime",   # MOV
}


class AppSettings(BaseSettings):
    """
    Root application settings aggregating all sub-settings.

    Usage:
        settings = get_settings()
        settings.database.async_url
        settings.minio.endpoint_url
    """

    model_config = SettingsConfigDict(env_prefix="APP_")

    environment: str = "development"  # "development", "staging", "production"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4

    # Allowed MIME types (comma-separated override)
    allowed_mime_types: str = ""

    # Sub-settings (instantiated from their own env prefixes)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    minio: MinIOSettings = Field(default_factory=MinIOSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    vault: VaultSettings = Field(default_factory=VaultSettings)
    tika: TikaSettings = Field(default_factory=TikaSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)

    @property
    def allowed_mime_type_set(self) -> Set[str]:
        """Return the resolved set of allowed MIME types."""
        if self.allowed_mime_types:
            return {m.strip() for m in self.allowed_mime_types.split(",") if m.strip()}
        return DEFAULT_ALLOWED_MIME_TYPES

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}, got '{v}'")
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Cached settings singleton.

    Reads from environment variables on first call.
    In production, ensure JWT_SECRET_KEY and DB_PASSWORD are set
    via environment or injected from Vault at startup.
    """
    # Set Tika env vars before any tika import can trigger JAR download
    os.environ.setdefault("TIKA_CLIENT_ONLY", "True")

    return AppSettings()
