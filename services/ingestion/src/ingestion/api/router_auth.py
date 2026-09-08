from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ingestion.config import get_settings
from ingestion.api.auth import create_access_token

router = APIRouter(prefix='/auth', tags=['Authentication'])

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    settings = get_settings()
    
    if not hasattr(settings.jwt, "dev_token_enabled") or not settings.jwt.dev_token_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token endpoint is disabled in production. Use your organization SSO."
        )
        
    if form_data.password != 'dev':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    permissions = ["admin:*"]
    access_token = create_access_token(
        subject=form_data.username,
        permissions=permissions
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.jwt.access_token_expire_minutes * 60
    }
