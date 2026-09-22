"""FastAPI dependency functions for authentication and role-based access control."""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import OperationalError, TimeoutError as DatabaseTimeoutError

from modules.shared.auth.models import UserInDB, UserRole
from modules.shared.auth.service import AuthService

# ── Shared instances ────────────────────────────────────────────────────────

# OAuth2 scheme — tells Swagger UI where to send credentials
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

# Singleton auth service (shared across all endpoints)
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Lazy-init singleton so the service is only created once."""
    global _auth_service
    if _auth_service is None:
        import os

        from sqlalchemy.engine import make_url
        from sqlalchemy.exc import ArgumentError

        try:
            url = os.getenv("AUTH_DATABASE_URL_SYNC") or os.getenv("DATABASE_URL_SYNC", "")
            configured = make_url(url).get_backend_name() == "postgresql"
        except (ArgumentError, ValueError):
            configured = False
        if not configured:
            raise HTTPException(
                503,
                "Shared authentication database is not configured. Start the application with the RDS configuration.",
            )
        from modules.shared.auth.postgres import PostgresAuthService

        _auth_service = PostgresAuthService()
    return _auth_service


# ── Dependency: current user ────────────────────────────────────────────────


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    auth: AuthService = Depends(get_auth_service),
) -> UserInDB:
    """Extract and validate the JWT from the Authorization header.

    Returns the authenticated UserInDB.
    Raises 401 if token is missing, invalid, or expired.
    """
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        verified = getattr(request.state, "verified_auth", None)
        payload = verified[1] if verified and verified[0] == token else auth.decode_token(token)
    except (OperationalError, DatabaseTimeoutError):
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# ── Dependency: require admin role ──────────────────────────────────────────


async def require_admin(
    user: UserInDB = Depends(get_current_user),
) -> UserInDB:
    """Gate that only allows admin-role users through.

    Raises 403 if the authenticated user is not an admin.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


# ── Dependency: require user role ───────────────────────────────────────────


async def require_user(
    user: UserInDB = Depends(get_current_user),
) -> UserInDB:
    """Gate that only allows user-role users through.

    Raises 403 if the authenticated user is not a regular user.
    """
    if user.role != UserRole.USER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User access required",
        )
    return user
