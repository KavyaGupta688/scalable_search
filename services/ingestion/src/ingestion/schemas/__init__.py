"""Pydantic schemas for request/response validation."""

from ingestion.schemas.connector import (
    ConnectorCreate,
    ConnectorResponse,
    ConnectorTestResponse,
    S3AuthenticationUpdate,
)
from ingestion.schemas.document import DocumentResponse, DocumentSearchParams
from ingestion.schemas.job import JobDescriptor, ProcessResult
from ingestion.schemas.metadata import DocumentMetadata
from ingestion.schemas.source_metadata import StructuredSourceMetadata
from ingestion.schemas.ingestion_run import IngestionRunItemResponse, IngestionRunResponse

__all__ = [
    "ConnectorCreate",
    "ConnectorResponse",
    "ConnectorTestResponse",
    "S3AuthenticationUpdate",
    "DocumentResponse",
    "DocumentSearchParams",
    "JobDescriptor",
    "ProcessResult",
    "DocumentMetadata",
    "StructuredSourceMetadata",
    "IngestionRunResponse",
    "IngestionRunItemResponse",
]
