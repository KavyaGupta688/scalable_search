from fastapi import APIRouter, Depends, Path
from app.schemas.file import FilePreviewResponse
from app.services.metadata_service import MetadataService
from app.core.dependencies import get_metadata_service
from app.core.security import get_current_user_context, UserContext

router = APIRouter()

@router.get("/{file_id}", response_model=FilePreviewResponse, summary="Get file metadata and AI preview details")
async def get_file_details(
    file_id: str = Path(..., description="Unique Document / File ID"),
    metadata_service: MetadataService = Depends(get_metadata_service),
    user: UserContext = Depends(get_current_user_context)
):
    """
    Returns full file metadata, technical properties, and AI-generated enrichment (captions, OCR, transcript, summary).
    """
    return await metadata_service.get_file_preview(file_id)
