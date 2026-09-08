from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ingestion.api.auth import RequirePermission
from ingestion.api.deps import get_async_session, get_minio_client
from ingestion.storage.minio_client import MinIOClient
from ingestion.models.document import Document
from ingestion.schemas.document import DocumentResponse, DocumentSearchParams, DocumentDownloadResponse

router = APIRouter(prefix='/documents', tags=['Documents'])

@router.get("/", response_model=List[DocumentResponse], dependencies=[Depends(RequirePermission('data:read'))])
async def search_documents(
    params: DocumentSearchParams = Depends(),
    db: AsyncSession = Depends(get_async_session)
):
    query = select(Document)
    
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
    documents = result.scalars().all()
    
    return [DocumentResponse.model_validate(doc) for doc in documents]

@router.get("/{document_id}", response_model=DocumentResponse, dependencies=[Depends(RequirePermission('data:read'))])
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_session)
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)

@router.get("/{document_id}/download", response_model=DocumentDownloadResponse, dependencies=[Depends(RequirePermission('data:download'))])
async def download_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_session),
    minio: MinIOClient = Depends(get_minio_client)
):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    expires_in = 3600
    presigned_url = await minio.generate_presigned_url(doc.storage_path, expires_in=expires_in)
    
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
