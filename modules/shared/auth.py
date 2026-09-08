"""Small, dependency-free RBAC layer for the local prototype."""
from __future__ import annotations
import base64, hashlib, hmac, json, os
from typing import Annotated
from fastapi import Depends, Header, HTTPException, status

ROLES = {"admin", "analyst", "viewer"}

def _secret() -> bytes:
    return os.getenv("JWT_SECRET_KEY", "prototype-only-change-me").encode()

def issue_token(email: str, role: str = "analyst") -> str:
    role = role if role in ROLES else "analyst"
    payload = json.dumps({"sub": email, "role": role}, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{body}." + hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()

def current_user(authorization: Annotated[str | None, Header()] = None) -> dict[str, str]:
    if not authorization:
        return {"sub": "demo@local", "role": "admin"}
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        body, signature = authorization[7:].split(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if payload.get("role") not in ROLES or not payload.get("sub"):
            raise ValueError
        return {"sub": str(payload["sub"]), "role": str(payload["role"])}
    except (ValueError, KeyError, json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from None

def require_roles(*roles: str):
    allowed = set(roles)
    def dependency(user: Annotated[dict[str, str], Depends(current_user)]) -> dict[str, str]:
        if user["role"] not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user
    return dependency
