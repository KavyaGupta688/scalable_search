from fastapi import APIRouter
from pydantic import BaseModel, Field
from modules.shared.auth import issue_token
from modules.shared.audit import record

router = APIRouter(prefix="/auth", tags=["auth"])

class TokenRequest(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=200)
    role: str = "analyst"

@router.post("/token")
def token(request: TokenRequest) -> dict[str, str | int]:
    record("login", request.email, "session", request.email, metadata={"role": request.role})
    return {"access_token": issue_token(request.email, request.role), "token_type": "bearer", "expires_in": 3600}
