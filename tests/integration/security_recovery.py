"""Real session expiry, cross-user job ownership, indexing replay and identity import checks."""

import json, os, tempfile, uuid
from pathlib import Path
import httpx
from sqlalchemy import text
from modules.shared.integration import database_engine
from modules.shared.auth.service import AuthService
from modules.shared.auth.models import RegisterRequest
from modules.shared.auth.postgres import PostgresAuthService
from scripts.import_legacy_identity import import_store
from modules.shared.indexer import index_document

c = httpx.Client(base_url="http://gateway:8000", timeout=60)
email = "ownership-" + uuid.uuid4().hex[:8] + "@example.com"
password = "Ownership-password-123"
assert (
    c.post(
        "/auth/register", json={"email": email, "password": password, "role": "user"}
    ).status_code
    == 200
)
login = c.post(
    "/auth/login", json={"email": email, "password": password, "role": "user"}
)
assert login.status_code == 200
h = {"Authorization": "Bearer " + login.json()["access_token"]}
with database_engine("download").connect() as db:
    job = db.execute(
        text("SELECT id FROM document_download_jobs WHERE status='ready' LIMIT 1")
    ).scalar_one()
for suffix in ("", "/content"):
    assert c.get("/downloads/" + job + suffix, headers=h).status_code == 404
with database_engine("identity").begin() as db:
    db.execute(
        text(
            "UPDATE auth_tokens SET expires_at='2000-01-01T00:00:00+00:00' WHERE user_id=(SELECT id FROM platform_users WHERE email=:e)"
        ),
        {"e": email},
    )
assert c.get("/auth/me", headers=h).status_code == 401
# Use a synthetic legacy store; never read the developer's existing data directory.
with tempfile.TemporaryDirectory() as tmp:
    users = Path(tmp) / "users.json"
    tokens = Path(tmp) / "auth.db"
    old_bootstrap = os.environ.pop("BOOTSTRAP_ADMIN_PASSWORD", None)
    try:
        old = AuthService(users, tokens)
        user = old.register(
            RegisterRequest(
                email="legacy-" + uuid.uuid4().hex[:8] + "@example.com",
                password=password,
                role="user",
            )
        )
        token = old.authenticate(user.email, password, user.role).access_token
        original = users.read_bytes()
        assert import_store(users, tokens) == (1, 1)
        assert import_store(users, tokens) == (1, 1)
        assert users.read_bytes() == original
        new = PostgresAuthService()
        assert new.decode_token(token)["sub"] == user.id
        new.revoke_token(token)
        try:
            new.decode_token(token)
        except ValueError:
            pass
        else:
            raise AssertionError("Revoked imported session accepted")
    finally:
        if old_bootstrap:
            os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = old_bootstrap
with database_engine("search").connect() as db:
    did = db.execute(
        text("SELECT file_id FROM file_metadata WHERE published=true LIMIT 1")
    ).scalar_one()
    before = db.execute(
        text("SELECT count(*) FROM file_metadata WHERE file_id=:id"), {"id": did}
    ).scalar()
index_document(did)
index_document(did)
with database_engine("search").connect() as db:
    assert (
        db.execute(
            text("SELECT count(*) FROM file_metadata WHERE file_id=:id"), {"id": did}
        ).scalar()
        == before
        == 1
    )
print(
    "PASS: cross-user job access denied, session expiry, non-destructive legacy identity import, revocation, idempotent projection replay"
)
