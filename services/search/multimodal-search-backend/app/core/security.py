from fastapi import Header, HTTPException, status
from typing import Optional
from pydantic import BaseModel

class UserContext(BaseModel):
    user_id: str = "usr_guest_demo"
    username: str = "demo_analyst"
    role: str = "ANALYST"  # ADMIN, ANALYST, VIEWER, AUDITOR
    department: str = "Geospatial & AI Systems"
    permissions: list[str] = ["search:read", "file:preview", "file:download", "events:write"]

async def get_current_user_context(
    x_user_id: Optional[str] = Header(default="usr_guest_demo"),
    x_user_role: Optional[str] = Header(default="ANALYST"),
    x_user_name: Optional[str] = Header(default="demo_analyst")
) -> UserContext:
    """
    Extracts authenticated user context from request headers (integrated with SSO gateway).
    """
    permissions_map = {
        "ADMIN": ["search:read", "file:preview", "file:download", "events:write", "admin:all"],
        "ANALYST": ["search:read", "file:preview", "file:download", "events:write"],
        "VIEWER": ["search:read", "file:preview", "events:write"],
        "AUDITOR": ["search:read", "file:preview", "audit:read", "events:write"]
    }
    
    perms = permissions_map.get(x_user_role.upper(), ["search:read", "file:preview"])
    return UserContext(
        user_id=x_user_id,
        username=x_user_name,
        role=x_user_role.upper(),
        permissions=perms
    )
