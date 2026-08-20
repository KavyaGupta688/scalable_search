from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class EnrichmentRequest(BaseModel):
    file_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)


@router.post("/enrich")
def enrich(request: EnrichmentRequest) -> dict[str, object]:
    stem = request.filename.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
    tags = [word.casefold() for word in stem.split() if len(word) > 2][:5]
    return {"file_id": request.file_id, "description": stem, "tags": tags, "status": "completed"}