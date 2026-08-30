"""Auth domain models — request/response schemas for the authentication API."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field


class UserRole(StrEnum):
    ADMIN = "admin"
    USER = "user"


# ── Request models ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    """POST /auth/login body."""
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    role: UserRole


class RegisterRequest(BaseModel):
    """POST /auth/register body."""
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.USER
    display_name: str = Field(default="", max_length=100)


# ── Response models ─────────────────────────────────────────────────────────

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    expires_in: int  # seconds


class UserResponse(BaseModel):
    id: str
    email: str
    role: UserRole
    display_name: str
    created_at: datetime


class UsersListResponse(BaseModel):
    users: list[UserResponse]
    total: int


# ── Internal model (never exposed via API) ──────────────────────────────────

class UserInDB(BaseModel):
    """Full user record including hashed password — never serialized to API."""
    id: str
    email: str
    role: UserRole
    display_name: str
    hashed_password: str
    created_at: datetime
