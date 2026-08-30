"""
Merge Tika-extracted metadata with system-generated metadata into
the canonical DocumentMetadata schema for DB persistence.
"""

from __future__ import annotations

from ingestion.schemas.metadata import SystemMetadata, DocumentMetadata


def normalize_metadata(system: SystemMetadata, tika: dict) -> DocumentMetadata:
    """
    Merge SystemMetadata + raw Tika dict into a canonical DocumentMetadata.

    Maps SystemMetadata.document_id → DocumentMetadata.id.
    Attaches the Tika dict as-is for storage in the JSONB column.
    """
    data = system.model_dump()
    # Rename document_id → id for the Document ORM model
    data["id"] = data.pop("document_id")
    data["tika_metadata"] = tika
    return DocumentMetadata(**data)
