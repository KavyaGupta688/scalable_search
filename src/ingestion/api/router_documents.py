from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.api.auth import RequirePermission
from ingestion.api.deps import get_async_session, get_minio_client
from ingestion.storage.minio_client import MinIOClient
from ingestion.models.document import Document
from ingestion.models.retention import LicenseEntitlement
from ingestion.schemas.document import DocumentResponse, DocumentSearchParams, DocumentDownloadResponse

router = APIRouter(prefix='/documents', tags=['Documents'])


def _document_response(doc: Document, entitlement: LicenseEntitlement) -> DocumentResponse:
    """Preserve the API contract while keeping licence facts normalized."""

    values = {
        column.name: getattr(doc, column.name) for column in Document.__table__.columns
    }
    values["first_successful_ingested_at"] = entitlement.license_start_at
    values["effective_expiry_at"] = entitlement.expires_at
    return DocumentResponse.model_validate(values)

@router.get("/", response_model=List[DocumentResponse], dependencies=[Depends(RequirePermission('data:read'))])
async def search_documents(
    params: DocumentSearchParams = Depends(),
    db: AsyncSession = Depends(get_async_session)
):
    query = select(Document, LicenseEntitlement).join(
        LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id
    )
    
    if hasattr(params, "mime_type") and params.mime_type:
        query = query.where(Document.mime_type == params.mime_type)
    if hasattr(params, "source_connector_id") and params.source_connector_id:
        query = query.where(Document.source_connector_id == params.source_connector_id)
        
    if hasattr(params, "limit"):
        limit = params.limit or 50
    else:
        limit = 50
        
    if hasattr(params, "offset"):
        offset = params.offset or 0
    else:
        offset = 0
        
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    rows = result.all()

    return [_document_response(doc, entitlement) for doc, entitlement in rows]

@router.get("/{document_id}", response_model=DocumentResponse, dependencies=[Depends(RequirePermission('data:read'))])
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(
        select(Document, LicenseEntitlement)
        .join(LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id)
        .where(Document.id == document_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    return _document_response(row[0], row[1])

@router.get("/{document_id}/download", response_model=DocumentDownloadResponse, dependencies=[Depends(RequirePermission('data:download'))])
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_session),
    minio: MinIOClient = Depends(get_minio_client)
):
    result = await db.execute(
        select(Document, LicenseEntitlement)
        .join(LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id)
        .where(Document.id == document_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    doc, entitlement = row
    now = datetime.now(timezone.utc)
    if doc.retention_status != "active" or entitlement.expires_at <= now:
        raise HTTPException(status_code=410, detail="Document content is no longer available")
    
    # Never issue a URL whose validity extends beyond the licensed deadline.
    expires_in = min(3600, int((entitlement.expires_at - now).total_seconds()))
    if expires_in < 1:
        raise HTTPException(status_code=410, detail="Document content is no longer available")
    presigned_url = await minio.generate_presigned_url(
        doc.storage_path,
        expires_in=expires_in,
        version_id=doc.object_version_id,
    )
    
    # Extract filename from storage_path or source_ref
    filename = doc.source_ref.rsplit("/", 1)[-1] if doc.source_ref else str(doc.id)
    
    return DocumentDownloadResponse(
        document_id=doc.id,
        download_url=presigned_url,
        expires_in_seconds=expires_in,
        filename=filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
    )
