"""
Application configuration via Pydantic Settings.

All configuration is environment-variable driven. No hardcoded secrets anywhere.
Group settings by concern for clarity.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
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


class ExternalMetadataSettings(BaseSettings):
    """Vendor manifest and sidecar metadata settings."""

    model_config = SettingsConfigDict(env_prefix="METADATA_")

    required: bool = True
    max_file_bytes: int = Field(32 * 1024 * 1024, ge=1)
    cache_max_directories: int = Field(1000, ge=1)
    manifest_names: str = "metadata.csv,metadata11.csv"
    sidecar_names: str = ".id,.desc,.tags,.lab,.cate"
    sidecars_with_manifest: bool = False
    additional_metadata_max_keys: int = Field(64, ge=0, le=1000)
    additional_metadata_max_bytes: int = Field(64 * 1024, ge=2)

    @property
    def manifest_name_list(self) -> tuple[str, ...]:
        return tuple(name.strip() for name in self.manifest_names.split(",") if name.strip())

    @property
    def sidecar_name_list(self) -> tuple[str, ...]:
        return tuple(name.strip() for name in self.sidecar_names.split(",") if name.strip())


class RetentionSettings(BaseSettings):
    """Licence-clock tracking for vendor-owned source content."""

    model_config = SettingsConfigDict(env_prefix="RETENTION_")

    enabled: bool = False
    dry_run: bool = True
    policy_years: int = Field(3, ge=1, le=100)
    reconciliation_interval_seconds: int = Field(900, ge=10)
    reconciliation_batch_size: int = Field(500, ge=1, le=10000)
    metrics_port: int = Field(9200, ge=0, le=65535)


class SourceAccessSettings(BaseSettings):
    """Credential-mode and short-lived source-access policy."""

    model_config = SettingsConfigDict(env_prefix="SOURCE_ACCESS_")

    allow_static_s3_credentials: bool = True
    presigned_url_seconds: int = Field(3600, ge=1, le=43200)


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
DEFAULT_ALLOWED_MIME_TYPES: set[str] = {
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
    "audio/mpeg",  # MP3
    "audio/wav",
    "audio/x-wav",
    # Video
    "video/mp4",
    "video/x-msvideo",  # AVI
    "video/quicktime",  # MOV
}


class AppSettings(BaseSettings):
    """
    Root application settings aggregating all sub-settings.

    Usage:
        settings = get_settings()
        settings.database.async_url
        settings.kafka.bootstrap_servers
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
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    vault: VaultSettings = Field(default_factory=VaultSettings)
    external_metadata: ExternalMetadataSettings = Field(default_factory=ExternalMetadataSettings)
    retention: RetentionSettings = Field(default_factory=RetentionSettings)
    source_access: SourceAccessSettings = Field(default_factory=SourceAccessSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)

    @property
    def allowed_mime_type_set(self) -> set[str]:
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
    return AppSettings()
