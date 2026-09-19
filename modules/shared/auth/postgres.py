"""PostgreSQL persistence for the redesigned credential and revocable-session contract."""

import json
import os
from contextlib import contextmanager
from sqlalchemy import text
from modules.shared.integration import database_engine
from modules.shared.auth.service import AuthService
from modules.shared.auth.models import UserInDB


def migrate():
    with database_engine("identity").begin() as conn:
        conn.execute(
            text("""CREATE TABLE IF NOT EXISTS platform_users (
            id text PRIMARY KEY, email text UNIQUE NOT NULL, data jsonb NOT NULL)""")
        )
        conn.execute(
            text("""CREATE TABLE IF NOT EXISTS auth_tokens (
            jti text PRIMARY KEY, user_id text NOT NULL, token_hash text UNIQUE NOT NULL,
            issued_at text NOT NULL, expires_at text NOT NULL, last_used_at text NOT NULL,
            revoked_at text)""")
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS auth_tokens_user_idx ON auth_tokens(user_id)"
            )
        )


class TokenConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, values=()):
        parts = statement.split("?")
        query = parts[0] + "".join(f":p{i}" + part for i, part in enumerate(parts[1:]))
        result = self.connection.execute(
            text(query), {f"p{i}": v for i, v in enumerate(values)}
        )
        return result.mappings() if result.returns_rows else result


class PostgresAuthService(AuthService):
    def _init_token_database(self):
        # Readiness check only: migration owns all DDL.
        with database_engine("identity").connect() as conn:
            conn.execute(text("SELECT jti FROM auth_tokens LIMIT 0"))

    @contextmanager
    def _connect_tokens(self):
        with database_engine("identity").begin() as conn:
            yield TokenConnection(conn)

    def _load(self):
        with database_engine("identity").connect() as conn:
            self._users = {
                row.id: UserInDB(**row.data)
                for row in conn.execute(text("SELECT id,data FROM platform_users"))
            }
        if not self._users and os.getenv("BOOTSTRAP_ADMIN_PASSWORD"):
            self._seed_initial_accounts()

    def _save(self):
        with database_engine("identity").begin() as conn:
            for user in self._users.values():
                conn.execute(
                    text("""INSERT INTO platform_users(id,email,data) VALUES (:id,:email,CAST(:data AS jsonb))
                    ON CONFLICT (id) DO NOTHING"""),
                    {
                        "id": user.id,
                        "email": user.email,
                        "data": user.model_dump_json(),
                    },
                )

    def register(self, request):
        import uuid
        from datetime import datetime, timezone
        from modules.shared.auth.service import _hash_password
        from sqlalchemy.exc import IntegrityError

        user = UserInDB(
            id="usr-" + uuid.uuid4().hex[:12],
            email=request.email.strip().lower(),
            role=request.role,
            display_name=request.display_name or request.email.split("@")[0],
            hashed_password=_hash_password(request.password),
            created_at=datetime.now(timezone.utc),
        )
        try:
            with database_engine("identity").begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO platform_users(id,email,data) VALUES (:id,:email,CAST(:data AS jsonb))"
                    ),
                    {
                        "id": user.id,
                        "email": user.email,
                        "data": user.model_dump_json(),
                    },
                )
        except IntegrityError:
            raise ValueError("Email is already registered") from None
        return self._to_response(user)

    def _find_by_email(self, email):
        with database_engine("identity").connect() as conn:
            data = conn.execute(
                text("SELECT data FROM platform_users WHERE email=:email"),
                {"email": email},
            ).scalar()
        return UserInDB(**data) if data else None

    def get_user(self, user_id):
        with database_engine("identity").connect() as conn:
            data = conn.execute(
                text("SELECT data FROM platform_users WHERE id=:id"), {"id": user_id}
            ).scalar()
        return UserInDB(**data) if data else None

    def list_users(self):
        self._load()
        return super().list_users()
