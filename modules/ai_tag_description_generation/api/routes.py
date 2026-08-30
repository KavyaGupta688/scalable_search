"""Prototype enrichment API; GPU workers remain under ``worker/pipeline``."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from modules.shared.auth import require_roles

router = APIRouter()

class EnrichmentRequest(BaseModel):
    file_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)

@router.post("/enrich", status_code=202)
def enrich(request: EnrichmentRequest, user: dict[str, str] = Depends(require_roles("admin", "analyst"))) -> dict[str, object]:
    stem = request.filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    tags = [word.casefold() for word in stem.split() if len(word) > 2][:8]
    return {"file_id": request.file_id, "description": stem, "tags": tags, "status": "completed", "model": "prototype"}

@router.get("/status/{file_id}")
def status(file_id: str, user: dict[str, str] = Depends(require_roles("admin", "analyst", "viewer"))) -> dict[str, str]:
    return {"file_id": file_id, "status": "completed", "current_stage": "metadata"}
