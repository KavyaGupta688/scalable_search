"""Read file locations and media metadata from the ingestion-owned table."""

from dataclasses import dataclass
import re
from uuid import UUID

from sqlalchemy import text

from modules.ai_tag_description_generation.app.config import settings
from modules.ai_tag_description_generation.app.db import get_async_session, get_sync_session


_SQL_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class SourceDocument:
    file_id: str
    storage_path: str
    file_type: str
    checksum: str
    source_metadata: dict


def _identifier(value: str) -> str:
    """Allow configuration to select identifiers without permitting SQL injection."""
    if not _SQL_IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid PostgreSQL identifier in source-table configuration: {value!r}")
    return value


def _source_query():
    schema = _identifier(settings.SOURCE_DOCUMENT_SCHEMA)
    table = _identifier(settings.SOURCE_DOCUMENT_TABLE)
    id_col = _identifier(settings.SOURCE_DOCUMENT_ID_COLUMN)
    path_col = _identifier(settings.SOURCE_STORAGE_PATH_COLUMN)
    type_col = _identifier(settings.SOURCE_FILE_TYPE_COLUMN)
    checksum_col = _identifier(settings.SOURCE_CHECKSUM_COLUMN)
    metadata_col = _identifier(settings.SOURCE_METADATA_COLUMN)
    return text(
        f"SELECT {id_col} AS file_id, {path_col} AS storage_path, "
        f"{type_col} AS file_type, {checksum_col} AS checksum, "
        f"{metadata_col} AS source_metadata FROM {schema}.{table} "
        f"WHERE {id_col} = :file_id"
    )


def _to_source_document(row) -> SourceDocument | None:
    if row is None:
        return None
    data = row._mapping
    if not data["storage_path"]:
        raise ValueError(f"Document {data['file_id']} has no MinIO storage path")
    return SourceDocument(
        file_id=str(data["file_id"]),
        storage_path=str(data["storage_path"]),
        file_type=str(data["file_type"] or ""),
        checksum=str(data["checksum"] or ""),
        source_metadata=data["source_metadata"] or {},
    )


async def get_source_document_async(file_id: str) -> SourceDocument | None:
    normalized_id = str(UUID(file_id))
    async with get_async_session() as session:
        result = await session.execute(_source_query(), {"file_id": normalized_id})
        return _to_source_document(result.first())


def get_source_document(file_id: str) -> SourceDocument | None:
    normalized_id = str(UUID(file_id))
    with get_sync_session() as session:
        result = session.execute(_source_query(), {"file_id": normalized_id})
        return _to_source_document(result.first())
