from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from modules.shared.auth.dependencies import get_current_user
from modules.shared.auth.models import UserInDB

router = APIRouter()


class DownloadRequest(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/batch", status_code=202)
def create_batch_download(
    request: DownloadRequest,
    _user: UserInDB = Depends(get_current_user),
) -> dict[str, object]:
    return {"download_id": "download-001", "status": "building", "file_count": len(request.file_ids)}


@router.get("/audit/events")
def audit_events(
    _user: UserInDB = Depends(get_current_user),
) -> dict[str, list[object]]:
    return {"events": []}


@router.get("/{download_id}")
def download_status(
    download_id: str,
    _user: UserInDB = Depends(get_current_user),
) -> dict[str, object]:
    return {"download_id": download_id, "status": "building", "updated_at": datetime.now(UTC)}