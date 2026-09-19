"""Credential authentication; compatibility dependencies for the audit module."""

from fastapi import Depends, HTTPException
from modules.shared.auth.dependencies import get_current_user


async def current_user(user=Depends(get_current_user)):
    return {"sub": user.id, "role": user.role, "email": user.email}


def require_roles(*roles):
    async def dependency(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "Insufficient role")
        return user

    return dependency
