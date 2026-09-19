"""Entitlement-aware client for the ingestion module's document boundary."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterator
from uuid import UUID
import hashlib

import httpx

from modules.ai_tag_description_generation.app.config import settings


class IngestionAccessError(RuntimeError):
    """The ingestion service denied or could not resolve source access."""


class SourceIntegrityError(ValueError):
    """Downloaded bytes do not match the canonical ingestion record."""


@dataclass(frozen=True)
class IngestionDocument:
    document_id: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    source_asset_id: str | None = None
    run_id: str | None = None
    entitlement_id: str | None = None
    source_type: str | None = None
    source_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if settings.INGESTION_API_TOKEN:
        headers["Authorization"] = f"Bearer {settings.INGESTION_API_TOKEN}"
    return headers


def _url(path: str) -> str:
    return f"{settings.INGESTION_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _raise_for_status(response: httpx.Response, action: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in (401, 403, 410):
            raise IngestionAccessError(f"Ingestion denied {action} (HTTP {status})") from exc
        raise IngestionAccessError(f"Ingestion could not {action} (HTTP {status})") from exc


def _metadata_from_document(payload: dict[str, Any], source_asset_id: str | None) -> dict[str, Any]:
    candidates = payload.get("metadata") or payload.get("document_metadata") or []
    if isinstance(candidates, dict):
        return candidates
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict) and str(item.get("source_asset_id")) == str(source_asset_id):
                return item
        if candidates and isinstance(candidates[0], dict):
            return candidates[0]
    return {}


def get_document(document_id: str, *, source_asset_id: str | None = None) -> IngestionDocument:
    """Read current canonical metadata without querying ingestion-owned tables."""
    normalized = str(UUID(document_id))
    with httpx.Client(timeout=settings.INGESTION_REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(_url(f"/documents/{normalized}"), headers=_headers())
    _raise_for_status(response, "read document metadata")
    payload = response.json()
    entitlement = payload.get("entitlement") or {}
    source = payload.get("source_asset") or {}
    return IngestionDocument(
        document_id=normalized,
        mime_type=str(payload.get("mime_type") or ""),
        size_bytes=int(payload.get("size_bytes") or 0),
        checksum_sha256=str(payload.get("checksum_sha256") or ""),
        source_asset_id=source_asset_id or source.get("id"),
        entitlement_id=payload.get("entitlement_id") or entitlement.get("id"),
        source_type=source.get("source_type"),
        source_ref=source.get("source_ref"),
        metadata=_metadata_from_document(payload, source_asset_id),
    )


def document_from_event(event: Any) -> IngestionDocument:
    """Build the immediate processing snapshot carried by ai-processing-events."""
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    return IngestionDocument(
        document_id=str(event.document_id),
        mime_type=event.mime_type,
        size_bytes=event.size_bytes,
        checksum_sha256=event.checksum_sha256,
        source_asset_id=str(event.source_asset_id),
        run_id=str(event.run_id),
        entitlement_id=str(event.entitlement_id),
        source_type=event.source_type,
        source_ref=event.source_ref,
        metadata=metadata,
    )


def _download_url(source: dict[str, Any], document_id: str) -> tuple[str, dict[str, str]]:
    mode = source.get("access_mode")
    if mode == "presigned_url":
        access_url = source.get("access_url")
        if not access_url:
            raise IngestionAccessError("Ingestion returned presigned_url without access_url")
        return str(access_url), {}
    if mode == "connector_stream":
        path = settings.INGESTION_CONTENT_PATH_TEMPLATE.format(document_id=document_id)
        return _url(path), _headers()
    raise IngestionAccessError(f"Unsupported ingestion access mode: {mode!r}")


@contextmanager
def materialize_document(document: IngestionDocument) -> Iterator[str]:
    """Stream source bytes to a bounded temporary file and verify size/hash."""
    if document.size_bytes < 0 or document.size_bytes > settings.MAX_SOURCE_BYTES:
        raise SourceIntegrityError(
            f"Document size {document.size_bytes} exceeds the configured source limit"
        )

    with httpx.Client(timeout=settings.INGESTION_REQUEST_TIMEOUT_SECONDS) as client:
        response = client.get(
            _url(f"/documents/{document.document_id}/source"),
            headers=_headers(),
        )
    _raise_for_status(response, "resolve document source")
    download_url, download_headers = _download_url(response.json(), document.document_id)

    suffix = Path(document.source_ref or "").suffix
    temporary_file = NamedTemporaryFile(suffix=suffix, delete=False)
    temporary_path = Path(temporary_file.name)
    temporary_file.close()
    digest = hashlib.sha256()
    observed_size = 0
    try:
        timeout = httpx.Timeout(settings.INGESTION_DOWNLOAD_TIMEOUT_SECONDS)
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            with client.stream("GET", download_url, headers=download_headers) as stream:
                _raise_for_status(stream, "stream document content")
                with temporary_path.open("wb") as destination:
                    for chunk in stream.iter_bytes():
                        observed_size += len(chunk)
                        if observed_size > settings.MAX_SOURCE_BYTES:
                            raise SourceIntegrityError("Source exceeded MAX_SOURCE_BYTES while streaming")
                        digest.update(chunk)
                        destination.write(chunk)

        if document.size_bytes and observed_size != document.size_bytes:
            raise SourceIntegrityError(
                f"Source size mismatch: expected {document.size_bytes}, received {observed_size}"
            )
        if document.checksum_sha256 and digest.hexdigest().lower() != document.checksum_sha256.lower():
            raise SourceIntegrityError("Source SHA-256 does not match the ingestion record")
        yield str(temporary_path)
    finally:
        temporary_path.unlink(missing_ok=True)
