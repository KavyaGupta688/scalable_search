from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class DownloadRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/batch", status_code=202)
def create_batch_download(request: DownloadRequest) -> dict[str, object]:
    return {"download_id": "download-001", "status": "building", "file_count": len(request.file_ids)}


@router.get("/audit/events")
def audit_events() -> dict[str, list[object]]:
    return {"events": []}


@router.get("/{download_id}")
def download_status(download_id: str) -> dict[str, object]:
    return {"download_id": download_id, "status": "building", "updated_at": datetime.now(UTC)}