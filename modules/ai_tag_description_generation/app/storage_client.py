"""Materialize MinIO objects as temporary local files for ML processors."""
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from minio import Minio

from app.config import settings


def _minio_client() -> Minio:
    if not all((settings.MINIO_ENDPOINT, settings.MINIO_ACCESS_KEY, settings.MINIO_SECRET_KEY)):
        raise RuntimeError(
            "MinIO is not configured. Set MINIO_ENDPOINT, MINIO_ACCESS_KEY, and MINIO_SECRET_KEY."
        )

    endpoint = settings.MINIO_ENDPOINT.strip()
    parsed = urlparse(endpoint)
    if parsed.scheme:
        endpoint = parsed.netloc
        secure = parsed.scheme == "https"
    else:
        secure = settings.MINIO_SECURE

    return Minio(
        endpoint,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=secure,
    )


def _parse_object_path(storage_path: str) -> tuple[str, str]:
    """Accept ``s3://bucket/key`` / ``minio://bucket/key`` / ``bucket/key``."""
    parsed = urlparse(storage_path)
    if parsed.scheme in {"s3", "minio"}:
        bucket, object_name = parsed.netloc, parsed.path.lstrip("/")
    elif not parsed.scheme:
        bucket, separator, object_name = storage_path.partition("/")
        if not separator:
            raise ValueError("MinIO storage_path must be bucket/object-name or s3://bucket/object-name")
    else:
        raise ValueError("Use an s3:// or minio:// URL, not an HTTP URL, for storage_path")

    if not bucket or not object_name:
        raise ValueError("MinIO storage_path must include both bucket and object name")
    return bucket, object_name


@contextmanager
def materialize_storage_path(storage_path: str):
    """Yield a local path, downloading a MinIO object only when necessary."""
    local_path = Path(storage_path)
    if local_path.is_file():
        yield str(local_path)
        return

    bucket, object_name = _parse_object_path(storage_path)
    suffix = Path(object_name).suffix
    temporary_file = NamedTemporaryFile(suffix=suffix, delete=False)
    temporary_path = Path(temporary_file.name)
    temporary_file.close()
    try:
        _minio_client().fget_object(bucket, object_name, str(temporary_path))
        yield str(temporary_path)
    finally:
        temporary_path.unlink(missing_ok=True)
