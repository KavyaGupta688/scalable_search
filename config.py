"""
Configuration module for the Download & Metadata Watermarking Gateway.
Supports environment variables, AWS S3, AWS RDS PostgreSQL / Aurora,
Celery/Redis background task queuing, and PostgreSQL enterprise database integration.
"""
import os
import sys
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent

# Ensure project root is in sys.path
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Auto-load .env file if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip("'\"")

# Cryptographic Secret for HMAC-SHA256 Signatures
HMAC_SECRET_KEY = os.getenv("WATERMARK_SECRET_KEY", "ENTERPRISE_SECURE_HMAC_KEY_2026_AGY")

# Explicit opt-in: native JPEG coefficient watermark plus existing metadata.
# Other formats retain their existing metadata behavior.
JPEG_CODEC_WATERMARK = os.getenv("JPEG_CODEC_WATERMARK", "false").lower() == "true"
LOSSLESS_SIGNAL_WATERMARK = os.getenv("LOSSLESS_SIGNAL_WATERMARK", "false").lower() == "true"
NATIVE_AUDIO_WATERMARK = os.getenv("NATIVE_AUDIO_WATERMARK", "false").lower() == "true"
NATIVE_VIDEO_WATERMARK = os.getenv("NATIVE_VIDEO_WATERMARK", "false").lower() == "true"
CODEC_WATERMARK_SECRET = os.getenv("CODEC_WATERMARK_SECRET", "")
if (JPEG_CODEC_WATERMARK or LOSSLESS_SIGNAL_WATERMARK or NATIVE_AUDIO_WATERMARK or NATIVE_VIDEO_WATERMARK) and len(CODEC_WATERMARK_SECRET.encode()) < 32:
    raise ValueError("Signal watermarking requires CODEC_WATERMARK_SECRET of at least 32 bytes")

# AWS S3 Configuration
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "demo-bucket-prism")

# Mock / Local S3 Mode (Set to False to connect to real S3)
USE_MOCK_S3 = os.getenv("USE_MOCK_S3", "false").lower() in ("true", "1", "yes")
LOCAL_MOCK_DIR = BASE_DIR / "sample_s3_data"

# Staging directory for async Celery watermarked packages
ASYNC_STORAGE_DIR = BASE_DIR / "async_downloads_staging"
ASYNC_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Database Configuration (AWS RDS PostgreSQL / Amazon Aurora / PostgreSQL)
AWS_RDS_HOST = os.getenv("AWS_RDS_HOST", os.getenv("POSTGRES_HOST", "localhost"))
AWS_RDS_PORT = os.getenv("AWS_RDS_PORT", os.getenv("POSTGRES_PORT", "5432"))
AWS_RDS_USER = os.getenv("AWS_RDS_USER", os.getenv("POSTGRES_USER", "postgres"))
AWS_RDS_PASSWORD = os.getenv("AWS_RDS_PASSWORD", os.getenv("POSTGRES_PASSWORD", "postgres"))
AWS_RDS_DB = os.getenv("AWS_RDS_DB", os.getenv("POSTGRES_DB", "watermark_db"))
AWS_RDS_SSLMODE = os.getenv("AWS_RDS_SSLMODE", "require" if "rds.amazonaws.com" in AWS_RDS_HOST else "prefer")

DEFAULT_PG_URL = f"postgresql://{AWS_RDS_USER}:{AWS_RDS_PASSWORD}@{AWS_RDS_HOST}:{AWS_RDS_PORT}/{AWS_RDS_DB}"
if "rds.amazonaws.com" in AWS_RDS_HOST and "?" not in DEFAULT_PG_URL:
    DEFAULT_PG_URL += f"?sslmode={AWS_RDS_SSLMODE}"

DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_PG_URL)

# Fallback SQLite DB path if PostgreSQL is unreachable during local testing
SQLITE_DB_PATH = BASE_DIR / "forensic_audit.db"

# Redis & Celery Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

# Server Configuration
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# Chunk size for S3 memory-efficient streaming (64 KB)
STREAM_CHUNK_SIZE = 64 * 1024
