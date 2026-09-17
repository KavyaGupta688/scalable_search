from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ingestion.api.auth import RequirePermission
from ingestion.api.deps import get_async_session, get_vault_service
from ingestion.models.document import Document, SourceAsset
from ingestion.models.retention import LicenseEntitlement
from ingestion.schemas.document import (
    DocumentResponse,
    DocumentSearchParams,
    DocumentSourceResponse,
    SourceAssetResponse,
)
from ingestion.services.source_access import generate_source_url
from ingestion.services.vault import VaultService

router = APIRouter(prefix="/documents", tags=["Documents"])


def _document_response(
    doc: Document,
    entitlement: LicenseEntitlement,
) -> DocumentResponse:
    values = {column.name: getattr(doc, column.name) for column in Document.__table__.columns}
    values["first_successful_ingested_at"] = entitlement.license_start_at
    values["effective_expiry_at"] = entitlement.expires_at
    values["entitlement_status"] = entitlement.status
    values["metadata"] = doc.structured_metadata
    return DocumentResponse.model_validate(values)


@router.get(
    "/",
    response_model=list[DocumentResponse],
    dependencies=[Depends(RequirePermission("data:read"))],
)
async def search_documents(
    params: DocumentSearchParams = Depends(),
    db: AsyncSession = Depends(get_async_session),
):
    query = select(Document, LicenseEntitlement).join(
        LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id
    ).options(selectinload(Document.structured_metadata))
    if params.mime_type:
        query = query.where(Document.mime_type == params.mime_type)
    if params.source_connector_id:
        query = query.where(
            Document.id.in_(
                select(SourceAsset.document_id).where(SourceAsset.source_connector_id == params.source_connector_id)
            )
        )
    if params.checksum:
        query = query.where(Document.checksum_sha256 == params.checksum)
    query = query.limit(params.page_size).offset((params.page - 1) * params.page_size)
    rows = (await db.execute(query)).all()
    return [_document_response(doc, entitlement) for doc, entitlement in rows]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    dependencies=[Depends(RequirePermission("data:read"))],
)
async def get_document(document_id: UUID, db: AsyncSession = Depends(get_async_session)):
    row = (
        await db.execute(
            select(Document, LicenseEntitlement)
            .join(LicenseEntitlement, Document.entitlement_id == LicenseEntitlement.id)
            .options(selectinload(Document.structured_metadata))
            .where(Document.id == document_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _document_response(row[0], row[1])


@router.get(
    "/{document_id}/sources",
    response_model=list[SourceAssetResponse],
    dependencies=[Depends(RequirePermission("data:read"))],
)
async def list_document_sources(document_id: UUID, db: AsyncSession = Depends(get_async_session)):
    assets = list(
        (
            await db.scalars(
                select(SourceAsset)
                .where(SourceAsset.document_id == document_id)
                .order_by(
                    SourceAsset.availability_status,
                    SourceAsset.last_verified_at.desc().nullslast(),
                )
            )
        ).all()
    )
    if not assets:
        raise HTTPException(status_code=404, detail="Document or source not found")
    return assets


@router.get(
    "/{document_id}/source",
    response_model=DocumentSourceResponse,
    dependencies=[Depends(RequirePermission("data:download"))],
)
@router.get(
    "/{document_id}/download",
    response_model=DocumentSourceResponse,
    dependencies=[Depends(RequirePermission("data:download"))],
    include_in_schema=False,
)
async def resolve_document_source(
    document_id: UUID,
    db: AsyncSession = Depends(get_async_session),
    vault: VaultService = Depends(get_vault_service),
):
    asset = await db.scalar(
        select(SourceAsset)
        .where(
            SourceAsset.document_id == document_id,
            SourceAsset.availability_status == "available",
        )
        .order_by(SourceAsset.last_verified_at.desc().nullslast())
        .limit(1)
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="No available source location")

    expires_in = 3600
    try:
        access_url = await generate_source_url(db, asset, vault, expires_in=expires_in)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Source access resolution failed") from exc

    return DocumentSourceResponse(
        document_id=document_id,
        source_asset=SourceAssetResponse.model_validate(asset),
        access_mode="presigned_url" if access_url else "connector_stream",
        access_url=access_url,
        expires_in_seconds=expires_in if access_url else None,
    )
