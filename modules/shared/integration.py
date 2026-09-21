"""Internal identity and database contracts shared by independently run services."""

from __future__ import annotations
import os
import re
import time
import uuid
from functools import lru_cache
from fastapi import Header, HTTPException
from jose import JWTError, jwt
from sqlalchemy import create_engine

USER_PERMISSIONS = ["search:read", "data:read", "data:download", "events:write"]


def signing_key() -> str:
    value = os.environ.get("INTERNAL_JWT_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("INTERNAL_JWT_SECRET must contain at least 32 characters")
    return value


def assertion(
    subject: str,
    role: str,
    audience: str,
    *,
    email: str = "",
    permissions: list[str] | None = None,
) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "sub": subject,
            "role": role,
            "email": email,
            "permissions": permissions
            if permissions is not None
            else (["admin:*"] if role == "admin" else USER_PERMISSIONS),
            "iss": "smsprsm",
            "aud": audience,
            "iat": now,
            "exp": now + 120,
            "jti": str(uuid.uuid4()),
        },
        signing_key(),
        algorithm="HS256",
    )


def verify_assertion(token: str, audience: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            signing_key(),
            algorithms=["HS256"],
            audience=audience,
            issuer="smsprsm",
            options={"require_exp": True, "require_sub": True, "require_iat": True},
        )
        if not isinstance(claims.get("permissions"), list):
            raise ValueError("Missing permissions")
        return claims
    except (JWTError, ValueError):
        raise HTTPException(401, "Invalid internal identity") from None


def internal_user(audience: str, permission: str | None = None):
    def dependency(authorization: str | None = Header(default=None)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Authentication required")
        claims = verify_assertion(authorization[7:], audience)
        if (
            permission
            and "admin:*" not in claims["permissions"]
            and permission not in claims["permissions"]
        ):
            raise HTTPException(403, "Insufficient permission")
        return claims

    return dependency


def service_headers(
    audience: str, permissions: list[str], subject: str = "worker"
) -> dict:
    return {
        "Authorization": "Bearer "
        + assertion(subject, "service", audience, permissions=permissions)
    }


def schema_name(default: str) -> str:
    value = os.environ.get("DATABASE_SCHEMA", default)
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", value):
        raise ValueError("Invalid database schema")
    return value


def connection_args(url: str, schema: str, *, asynchronous: bool = False) -> dict:
    if not url.startswith("postgresql"):
        return {}
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
        raise ValueError("Invalid database schema")
    return (
        {"server_settings": {"search_path": schema}}
        if asynchronous
        else {"options": f"-csearch_path={schema}"}
    )


@lru_cache
def database_engine(schema: str):
    # Identity can be shared across independently configured module stacks.
    configured_url = os.getenv("AUTH_DATABASE_URL_SYNC") if schema == "identity" else None
    url = (configured_url or os.environ["DATABASE_URL_SYNC"]).replace(
        "postgresql://", "postgresql+psycopg2://"
    )
    args = connection_args(url, schema)
    if url.startswith("postgresql"):
        args["connect_timeout"] = 5
    options = {"pool_timeout": 5} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=args, **options)


def point_id(document_id: str) -> str:
    return str(uuid.UUID(str(document_id)))
