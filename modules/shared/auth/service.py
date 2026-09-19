"""AuthService — handles user registration, authentication, JWT creation, and persistence."""

import json
import hashlib
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

import bcrypt
from jose import jwt

from modules.shared.auth.models import (
    LoginResponse,
    RegisterRequest,
    UserInDB,
    UserResponse,
    UserRole,
)

# ── Configuration ───────────────────────────────────────────────────────────

JWT_SECRET = os.getenv("NEXUS_JWT_SECRET", "nexus-enterprise-secure-jwt-token-secret-key-2026-auth")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.getenv("NEXUS_DATA_DIR", str(PROJECT_ROOT / "data")))
USERS_FILE = DATA_DIR / "users.json"
AUTH_DB_FILE = Path(os.getenv("NEXUS_AUTH_DB", str(DATA_DIR / "auth.db")))

# ── Password hashing (direct bcrypt) ───────────────────────────────────────


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt with auto-generated salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class AuthService:
    """Persistent users and database-backed JWT sessions."""

    def __init__(
        self,
        users_file: Path = USERS_FILE,
        auth_db_file: Path = AUTH_DB_FILE,
    ) -> None:
        self._users_file = users_file
        self._auth_db_file = auth_db_file
        self._users: dict[str, UserInDB] = {}
        self._init_token_database()
        self._load()

    # ── Public API ──────────────────────────────────────────────────────────

    def register(self, request: RegisterRequest) -> UserResponse:
        """Create a new user account. Raises ValueError if email is taken."""
        email_lower = request.email.strip().lower()

        if any(u.email == email_lower for u in self._users.values()):
            raise ValueError(f"Email '{email_lower}' is already registered")

        user_id = f"usr-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        user = UserInDB(
            id=user_id,
            email=email_lower,
            role=request.role,
            display_name=request.display_name or email_lower.split("@")[0],
            hashed_password=_hash_password(request.password),
            created_at=now,
        )
        self._users[user_id] = user
        self._save()

        return self._to_response(user)

    def authenticate(self, email: str, password: str, role: UserRole) -> LoginResponse:
        """Verify credentials and role, return a signed JWT.

        Raises ValueError on invalid credentials or role mismatch.
        """
        email_lower = email.strip().lower()
        user = self._find_by_email(email_lower)

        if user is None:
            raise ValueError("Invalid email or password")

        if not _verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if user.role != role:
            raise ValueError(
                f"This account is registered as '{user.role}'. "
                f"Please use the {user.role} login page."
            )

        token = self._create_token(user.id, user.role)
        return LoginResponse(
            access_token=token,
            role=user.role,
            expires_in=JWT_EXPIRE_HOURS * 3600,
        )

    def get_user(self, user_id: str) -> UserInDB | None:
        """Look up a user by ID."""
        return self._users.get(user_id)

    def list_users(self) -> list[UserResponse]:
        """Return all registered users (admin use only)."""
        return [self._to_response(u) for u in self._users.values()]

    def decode_token(self, token: str) -> dict:
        """Decode a JWT and require its active session to exist in the database.

        Raises JWTError on invalid/expired tokens.
        """
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        token_id = payload.get("jti")
        if not token_id or not self._is_token_active(token_id, token):
            raise ValueError("Token session is missing, expired, or revoked")
        self._touch_token(token_id)
        return payload

    def revoke_token(self, token: str) -> None:
        """Revoke a persisted JWT session. Invalid tokens are ignored."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        except Exception:
            return
        token_id = payload.get("jti")
        if not token_id:
            return
        with self._connect_tokens() as connection:
            connection.execute(
                "UPDATE auth_tokens SET revoked_at = ? WHERE jti = ? AND token_hash = ?",
                (self._now_iso(), token_id, self._token_hash(token)),
            )

    def token_status(self, token: str) -> dict[str, object]:
        """Return safe persistence metadata for the supplied JWT."""
        payload = self.decode_token(token)
        with self._connect_tokens() as connection:
            row = connection.execute(
                """
                SELECT jti, user_id, issued_at, expires_at, last_used_at
                FROM auth_tokens WHERE jti = ?
                """,
                (payload["jti"],),
            ).fetchone()
        return {
            "stored": row is not None,
            "jti": row["jti"],
            "user_id": row["user_id"],
            "issued_at": row["issued_at"],
            "expires_at": row["expires_at"],
            "last_used_at": row["last_used_at"],
        }

    # ── Private helpers ─────────────────────────────────────────────────────

    def _find_by_email(self, email: str) -> UserInDB | None:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def _create_token(self, user_id: str, role: UserRole) -> str:
        issued_at = datetime.now(UTC)
        expire = issued_at + timedelta(hours=JWT_EXPIRE_HOURS)
        token_id = str(uuid.uuid4())
        payload = {
            "sub": user_id,
            "role": str(role),
            "jti": token_id,
            "iat": issued_at,
            "exp": expire,
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
        with self._connect_tokens() as connection:
            connection.execute(
                """
                INSERT INTO auth_tokens
                    (jti, user_id, token_hash, issued_at, expires_at, last_used_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token_id,
                    user_id,
                    self._token_hash(token),
                    issued_at.isoformat(),
                    expire.isoformat(),
                    issued_at.isoformat(),
                ),
            )
        return token

    def _init_token_database(self) -> None:
        self._auth_db_file.parent.mkdir(parents=True, exist_ok=True)
        with self._connect_tokens() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    jti TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL,
                    revoked_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON auth_tokens(user_id)"
            )

    @contextmanager
    def _connect_tokens(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._auth_db_file, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _is_token_active(self, token_id: str, token: str) -> bool:
        with self._connect_tokens() as connection:
            row = connection.execute(
                """
                SELECT expires_at FROM auth_tokens
                WHERE jti = ? AND token_hash = ? AND revoked_at IS NULL
                """,
                (token_id, self._token_hash(token)),
            ).fetchone()
        if row is None:
            return False
        return datetime.fromisoformat(row["expires_at"]) > datetime.now(UTC)

    def _touch_token(self, token_id: str) -> None:
        with self._connect_tokens() as connection:
            connection.execute(
                "UPDATE auth_tokens SET last_used_at = ? WHERE jti = ?",
                (self._now_iso(), token_id),
            )

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _to_response(user: UserInDB) -> UserResponse:
        return UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            display_name=user.display_name,
            created_at=user.created_at,
        )

    # ── Persistence ─────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load users from JSON file, or seed initial accounts if file missing."""
        if self._users_file.exists():
            try:
                raw = json.loads(self._users_file.read_text(encoding="utf-8"))
                for uid, data in raw.items():
                    self._users[uid] = UserInDB(**data)
                return
            except (json.JSONDecodeError, Exception):
                pass  # Fall through to seeding

        self._seed_initial_accounts()

    def _seed_initial_accounts(self) -> None:
        """Create initial admin and user accounts for local installation."""
        now = datetime.now(UTC)

        admin = UserInDB(
            id="usr-seed-admin-01",
            email="admin@platform.internal",
            role=UserRole.ADMIN,
            display_name="Administrator",
            hashed_password=_hash_password("admin123"),
            created_at=now,
        )
        user = UserInDB(
            id="usr-seed-user-01",
            email="user@platform.internal",
            role=UserRole.USER,
            display_name="Standard User",
            hashed_password=_hash_password("user123"),
            created_at=now,
        )
        self._users[admin.id] = admin
        self._users[user.id] = user
        self._save()

    def _save(self) -> None:
        """Persist the user store to disk as JSON."""
        serialized = {
            uid: u.model_dump(mode="json") for uid, u in self._users.items()
        }
        self._users_file.parent.mkdir(parents=True, exist_ok=True)
        self._users_file.write_text(
            json.dumps(serialized, indent=2, default=str),
            encoding="utf-8",
        )
