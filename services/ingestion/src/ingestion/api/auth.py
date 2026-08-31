from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import List

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

from ingestion.config import get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/auth/token')


class TokenPayload(BaseModel):
    sub: str
    permissions: List[str]
    exp: int
    iat: int


async def get_current_token_payload(token: str = Depends(oauth2_scheme)) -> TokenPayload:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt.secret_key,
            algorithms=["HS256"]
        )
        token_data = TokenPayload(**payload)
        if token_data.exp < int(time.time()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )
        return token_data
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


class RequirePermission:
    def __init__(self, *required_permissions: str):
        self.required_permissions = required_permissions

    def __call__(self, payload: TokenPayload = Depends(get_current_token_payload)) -> TokenPayload:
        if "admin:*" in payload.permissions:
            return payload
            
        for permission in self.required_permissions:
            if permission not in payload.permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {permission}"
                )
        return payload


def create_access_token(subject: str, permissions: List[str], expires_delta: timedelta = None) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt.access_token_expire_minutes)
        
    to_encode = {
        "sub": subject,
        "permissions": permissions,
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    encoded_jwt = jwt.encode(to_encode, settings.jwt.secret_key, algorithm="HS256")
    return encoded_jwt
