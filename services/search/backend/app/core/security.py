from fastapi import Depends
from pydantic import BaseModel
from modules.shared.integration import internal_user


class UserContext(BaseModel):
    user_id: str
    username: str
    role: str
    permissions: list[str]


async def get_current_user_context(
    claims=Depends(internal_user("search", "search:read")),
):
    return UserContext(
        user_id=claims["sub"],
        username=claims.get("email") or claims["sub"],
        role=claims["role"],
        permissions=claims["permissions"],
    )
