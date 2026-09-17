"""Read and normalize vendor-supplied CSV and sidecar metadata."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import OrderedDict
from pathlib import PurePosixPath

from ingestion.config import ExternalMetadataSettings, get_settings
from ingestion.connectors.base import ConnectorError, SourceConnector
from ingestion.monitoring.logging import get_logger
from ingestion.schemas.job import JobDescriptor
from ingestion.schemas.source_metadata import StructuredSourceMetadata
from ingestion.worker.validator import PermanentProcessingError

logger = get_logger(__name__)

_MANIFEST_CACHE: OrderedDict[
    tuple[str, str, str | None], dict[str, tuple[list[dict[str, str]], str]]
] = OrderedDict()


def is_metadata_control_file(job: JobDescriptor) -> bool:
    settings = get_settings().external_metadata
    name = PurePosixPath(_relative_path(job)).name
    return name in settings.manifest_name_list or name in settings.sidecar_name_list


def _relative_path(job: JobDescriptor) -> str:
    if job.source_type == "S3":
        return (job.object_key or job.source_ref.split("/", 1)[-1]).replace("\\", "/")
    return (job.relative_path or job.source_ref).replace("\\", "/").lstrip("/")


def _metadata_job(job: JobDescriptor, relative_path: str) -> JobDescriptor:
    relative_path = relative_path.replace("\\", "/").lstrip("/")
    if job.source_type == "S3":
        bucket = job.bucket or job.source_ref.split("/", 1)[0]
        return job.model_copy(
            update={
                "source_ref": f"{bucket}/{relative_path}",
                "bucket": bucket,
                "object_key": relative_path,
                "relative_path": None,
                "size_bytes": None,
                "etag": None,
                "version_id": None,
                "provisional_id": f"metadata:{relative_path}",
            }
        )

    original_relative = _relative_path(job)
    source_prefix = job.source_ref[: -len(original_relative)] if original_relative else ""
    return job.model_copy(
        update={
            "source_ref": f"{source_prefix}{relative_path}",
            "relative_path": relative_path,
            "size_bytes": None,
            "mtime": None,
            "provisional_id": f"metadata:{relative_path}",
        }
    )


def _missing_metadata_file(exc: Exception) -> bool:
    message = str(exc).casefold()
    return any(
        marker in message
        for marker in (
            "nosuchkey",
            "not found",
            "cannot find the file",
            "status_object_name_not_found",
            "0xc0000034",
        )
    )


async def _read_small_text(
    connector: SourceConnector,
    job: JobDescriptor,
    relative_path: str,
    settings: ExternalMetadataSettings,
) -> tuple[str, str] | None:
    metadata_job = _metadata_job(job, relative_path)
    content = bytearray()
    try:
        async for chunk in connector.open_stream(metadata_job):
            content.extend(chunk)
            if len(content) > settings.max_file_bytes:
                raise PermanentProcessingError(
                    f"Metadata file exceeds METADATA_MAX_FILE_BYTES: {metadata_job.source_ref}"
                )
    except ConnectorError as exc:
        if _missing_metadata_file(exc):
            return None
        raise
    try:
        return content.decode("utf-8-sig"), metadata_job.source_ref
    except UnicodeDecodeError as exc:
        raise PermanentProcessingError(
            f"Metadata file is not valid UTF-8: {metadata_job.source_ref}"
        ) from exc


def _manifest_directories(job: JobDescriptor) -> list[str]:
    directory = PurePosixPath(_relative_path(job)).parent
    values: list[str] = []
    while True:
        value = "" if str(directory) == "." else str(directory)
        values.append(value)
        if not value:
            return values
        directory = directory.parent


async def _load_manifests(
    connector: SourceConnector,
    job: JobDescriptor,
    directory: str,
    settings: ExternalMetadataSettings,
) -> dict[str, tuple[list[dict[str, str]], str]]:
    cache_key = (str(job.connector_id), directory, str(job.run_id) if job.run_id else None)
    use_cache = job.run_id is not None
    if use_cache and cache_key in _MANIFEST_CACHE:
        _MANIFEST_CACHE.move_to_end(cache_key)
        return _MANIFEST_CACHE[cache_key]

    manifests: dict[str, tuple[list[dict[str, str]], str]] = {}
    for name in settings.manifest_name_list:
        path = f"{directory}/{name}" if directory else name
        loaded = await _read_small_text(connector, job, path, settings)
        if loaded is None:
            continue
        text, source_ref = loaded
        try:
            reader = csv.DictReader(io.StringIO(text))
            rows = [
                {str(key).strip(): (value or "").strip() for key, value in row.items() if key}
                for row in reader
            ]
        except csv.Error as exc:
            raise PermanentProcessingError(f"Malformed CSV metadata: {source_ref}") from exc
        manifests[name] = (rows, source_ref)

    if use_cache:
        _MANIFEST_CACHE[cache_key] = manifests
        _MANIFEST_CACHE.move_to_end(cache_key)
        while len(_MANIFEST_CACHE) > settings.cache_max_directories:
            _MANIFEST_CACHE.popitem(last=False)
    return manifests


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


def _values(value: str | None, separators: str = r"[|,]") -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in re.split(separators, value or ""):
        cleaned = item.strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _merge_unique(existing: list[str], additions: list[str]) -> list[str]:
    seen = {item.casefold() for item in existing}
    for item in additions:
        if item.casefold() not in seen:
            existing.append(item)
            seen.add(item.casefold())
    return existing


def _target_matches(target: str, job: JobDescriptor) -> bool:
    normalized = target.replace("\\", "/").strip().casefold()
    normalized = re.sub(r"^[a-z][a-z0-9+.-]*://", "", normalized)
    candidates = {_relative_path(job).casefold(), job.source_ref.replace("\\", "/").casefold()}
    return any(normalized == candidate or normalized.endswith(f"/{candidate}") for candidate in candidates)


_MAPPED_OR_IGNORED_FIELDS = {
    "id",
    "asset_id",
    "filename",
    "target_path",
    "title",
    "description",
    "category",
    "primary_category",
    "tags",
    "labels",
    "keywords",
    "categories",
    "brand",
    "contributor_id",
    # Explicitly excluded client-unneeded/image-specific fields.
    "width",
    "height",
    "file_size_bytes",
    "mime_type",
    "camera_make",
    "camera_model",
    "location_name",
    "gps_lat",
    "gps_lon",
    "taken_at",
    "uploaded_at",
    "view_count",
    "download_count",
    "image_type",
}


def _coerce_additional_value(value: str) -> str | int | float | bool | None:
    cleaned = value.strip()
    lowered = cleaned.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?(0|[1-9]\d*)", cleaned):
        return int(cleaned)
    if re.fullmatch(r"-?(0|[1-9]\d*)\.\d+", cleaned):
        return float(cleaned)
    return cleaned


def _capture_additional(values: dict, row: dict[str, str]) -> None:
    additional = values["additional_metadata"]
    for raw_key, raw_value in row.items():
        key = raw_key.strip().casefold()
        value = _clean(raw_value)
        if not key or key in _MAPPED_OR_IGNORED_FIELDS or value is None:
            continue
        additional[key] = _coerce_additional_value(value)


def _apply_metadata_csv(values: dict, row: dict[str, str]) -> None:
    values.update(
        external_asset_id=_clean(row.get("id")) or values.get("external_asset_id"),
        title=_clean(row.get("title")) or values.get("title"),
        description=_clean(row.get("description")) or values.get("description"),
        primary_category=_clean(row.get("category")) or values.get("primary_category"),
    )
    values["tags"] = _merge_unique(values["tags"], _values(row.get("tags"), r"\|"))
    values["tags"] = _merge_unique(values["tags"], _values(row.get("keywords")))
    values["categories"] = _merge_unique(values["categories"], _values(row.get("categories")))
    _capture_additional(values, row)


def _apply_stock_csv(values: dict, row: dict[str, str]) -> None:
    values.update(
        external_asset_id=_clean(row.get("asset_id")) or values.get("external_asset_id"),
        title=_clean(row.get("title")) or values.get("title"),
        brand=_clean(row.get("brand")),
        description=_clean(row.get("description")) or values.get("description"),
        primary_category=_clean(row.get("primary_category")) or values.get("primary_category"),
        contributor_id=_clean(row.get("contributor_id")),
    )
    values["tags"] = _merge_unique(values["tags"], _values(row.get("tags")))
    values["tags"] = _merge_unique(values["tags"], _values(row.get("keywords")))
    values["categories"] = _merge_unique(values["categories"], _values(row.get("categories")))
    _capture_additional(values, row)


async def resolve_source_metadata(
    connector: SourceConnector, job: JobDescriptor
) -> StructuredSourceMetadata | None:
    settings = get_settings().external_metadata
    filename = PurePosixPath(_relative_path(job)).name
    values: dict = {
        "metadata_formats": [],
        "metadata_source_refs": [],
        "tags": [],
        "categories": [],
        "additional_metadata": {},
    }

    for directory in _manifest_directories(job):
        manifests = await _load_manifests(connector, job, directory, settings)
        for rows, source_ref in manifests.values():
            headers = set(rows[0]) if rows else set()
            if "filename" not in headers:
                continue
            row = next(
                (row for row in rows if (row.get("filename") or "").casefold() == filename.casefold()),
                None,
            )
            if row:
                _apply_metadata_csv(values, row)
                values["metadata_formats"].append("metadata_csv")
                values["metadata_source_refs"].append(source_ref)
        for rows, source_ref in manifests.values():
            headers = set(rows[0]) if rows else set()
            if "target_path" not in headers:
                continue
            row = next((row for row in rows if _target_matches(row.get("target_path", ""), job)), None)
            if row:
                _apply_stock_csv(values, row)
                values["metadata_formats"].append("stock_csv")
                values["metadata_source_refs"].append(source_ref)

    sidecars: dict[str, str] = {}
    if not values["metadata_formats"] or settings.sidecars_with_manifest:
        asset_directory = str(PurePosixPath(_relative_path(job)).parent)
        if asset_directory == ".":
            asset_directory = ""
        for name in settings.sidecar_name_list:
            path = f"{asset_directory}/{name}" if asset_directory else name
            loaded = await _read_small_text(connector, job, path, settings)
            if loaded:
                text, source_ref = loaded
                sidecars[name] = text.strip()
                values["metadata_source_refs"].append(source_ref)
    if sidecars:
        values["metadata_formats"].append("sidecar")
        values["external_asset_id"] = _clean(sidecars.get(".id")) or values.get(
            "external_asset_id"
        )
        values["description"] = _clean(sidecars.get(".desc")) or values.get("description")
        values["primary_category"] = _clean(sidecars.get(".cate")) or values.get("primary_category")
        values["tags"] = _merge_unique(values["tags"], _values(sidecars.get(".tags")))
        values["tags"] = _merge_unique(values["tags"], _values(sidecars.get(".lab")))

    values["metadata_formats"] = list(dict.fromkeys(values["metadata_formats"]))
    values["metadata_source_refs"] = list(dict.fromkeys(values["metadata_source_refs"]))
    if not values["metadata_formats"]:
        if settings.required:
            raise PermanentProcessingError(
                f"No vendor metadata matched source file {job.source_ref}"
            )
        return None
    additional = values["additional_metadata"]
    if len(additional) > settings.additional_metadata_max_keys:
        raise PermanentProcessingError(
            "Vendor additional metadata exceeds METADATA_ADDITIONAL_METADATA_MAX_KEYS"
        )
    encoded_additional = json.dumps(additional, separators=(",", ":")).encode("utf-8")
    if len(encoded_additional) > settings.additional_metadata_max_bytes:
        raise PermanentProcessingError(
            "Vendor additional metadata exceeds METADATA_ADDITIONAL_METADATA_MAX_BYTES"
        )
    return StructuredSourceMetadata.model_validate(values)


def clear_metadata_cache() -> None:
    _MANIFEST_CACHE.clear()
