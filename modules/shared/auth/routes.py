"""Auth API routes — login, register, profile, and user listing."""

from fastapi import APIRouter, Depends, HTTPException, status

from modules.shared.auth.dependencies import (
    get_auth_service,
    get_current_user,
    require_admin,
)
from modules.shared.auth.models import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserInDB,
    UserResponse,
    UsersListResponse,
)
from modules.shared.auth.service import AuthService

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(
    request: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
) -> LoginResponse:
    """Authenticate a user and return a signed JWT."""
    try:
        return auth.authenticate(request.email, request.password, request.role)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/register", response_model=UserResponse)
def register(
    request: RegisterRequest,
    auth: AuthService = Depends(get_auth_service),
) -> UserResponse:
    """Create a new user account."""
    try:
        return auth.register(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get("/me", response_model=UserResponse)
def me(user: UserInDB = Depends(get_current_user)) -> UserResponse:
    """Return the current authenticated user's profile."""
    return UserResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        created_at=user.created_at,
    )


@router.get("/users", response_model=UsersListResponse)
def list_users(
    _admin: UserInDB = Depends(require_admin),
    auth: AuthService = Depends(get_auth_service),
) -> UsersListResponse:
    """List all registered users (admin only)."""
    users = auth.list_users()
    return UsersListResponse(users=users, total=len(users))
