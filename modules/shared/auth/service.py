"""AuthService — handles user registration, authentication, JWT creation, and persistence."""

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

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

JWT_SECRET = os.getenv("NEXUS_JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24

# If no secret is set, generate a random one (tokens won't survive restarts).
if not JWT_SECRET:
    JWT_SECRET = uuid.uuid4().hex + uuid.uuid4().hex  # 64-char random key

DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"

# ── Password hashing (direct bcrypt) ───────────────────────────────────────


def _hash_password(password: str) -> str:
    """Hash a password using bcrypt with auto-generated salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


class AuthService:
    """In-memory user store with JSON file persistence and JWT authentication."""

    def __init__(self) -> None:
        self._users: dict[str, UserInDB] = {}
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
        """Decode and validate a JWT. Returns the payload dict.

        Raises JWTError on invalid/expired tokens.
        """
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])

    # ── Private helpers ─────────────────────────────────────────────────────

    def _find_by_email(self, email: str) -> UserInDB | None:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def _create_token(self, user_id: str, role: UserRole) -> str:
        expire = datetime.now(UTC) + timedelta(hours=JWT_EXPIRE_HOURS)
        payload = {
            "sub": user_id,
            "role": str(role),
            "exp": expire,
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

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
        """Load users from JSON file, or seed demo accounts if file missing."""
        if USERS_FILE.exists():
            try:
                raw = json.loads(USERS_FILE.read_text(encoding="utf-8"))
                for uid, data in raw.items():
                    self._users[uid] = UserInDB(**data)
                return
            except (json.JSONDecodeError, Exception):
                pass  # Fall through to seeding

        # Seed demo accounts
        self._seed_demo_accounts()

    def _seed_demo_accounts(self) -> None:
        """Create default admin and user accounts for development."""
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
            display_name="Demo User",
            hashed_password=_hash_password("user123"),
            created_at=now,
        )
        self._users[admin.id] = admin
        self._users[user.id] = user
        self._save()

    def _save(self) -> None:
        """Persist the user store to disk as JSON."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        serialized = {
            uid: u.model_dump(mode="json") for uid, u in self._users.items()
        }
        USERS_FILE.write_text(
            json.dumps(serialized, indent=2, default=str),
            encoding="utf-8",
        )
