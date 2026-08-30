from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from modules.shared.auth.dependencies import require_admin
from modules.shared.auth.models import UserInDB

router = APIRouter()
ALLOWED_DOCUMENT_TYPES = {"application/pdf", "text/plain", "text/csv", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
jobs: dict[str, dict[str, object]] = {}


class IngestionRequest(BaseModel):
    filename: str = Field(min_length=1)
    content_type: str = Field(min_length=1)


@router.post("", status_code=202)
def start_ingestion(
    request: IngestionRequest,
    _admin: UserInDB = Depends(require_admin),
) -> dict[str, object]:
    job = {"ingestion_id": "ingestion-001", "filename": request.filename, "content_type": request.content_type, "status": "queued"}
    jobs["ingestion-001"] = job
    return job


@router.post("/upload", status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    _admin: UserInDB = Depends(require_admin),
) -> dict[str, object]:
    if file.content_type not in ALLOWED_DOCUMENT_TYPES:
        raise HTTPException(status_code=415, detail="Supported documents are PDF, DOCX, TXT, and CSV")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The selected document is empty")
    ingestion_id = f"ingestion-{len(jobs) + 1:03d}"
    job = {
        "ingestion_id": ingestion_id,
        "filename": file.filename or "untitled",
        "content_type": file.content_type,
        "size_bytes": len(content),
        "status": "queued",
        "pipeline": {"extraction": "queued", "ai_enrichment": "queued", "indexing": "queued"},
    }
    jobs[ingestion_id] = job
    return job


@router.get("/{ingestion_id}")
def ingestion_status(
    ingestion_id: str,
    _admin: UserInDB = Depends(require_admin),
) -> dict[str, object]:
    job = jobs.get(ingestion_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Ingestion job not found")
    return job