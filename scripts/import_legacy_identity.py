"""Import an explicitly supplied redesigned identity store without changing its files.

Run after migrations and before the first gateway boot. Conflicting existing identities
abort the transaction. Keeping the old signing key preserves unexpired sessions.
"""

import argparse, json, sqlite3
from pathlib import Path
from sqlalchemy import text
from modules.shared.auth.models import UserInDB
from modules.shared.integration import database_engine


def import_store(users_path, tokens_path=None):
    users = [
        UserInDB(**d)
        for d in json.loads(Path(users_path).read_text(encoding="utf-8")).values()
    ]
    tokens = []
    if tokens_path:
        source = Path(tokens_path).resolve()
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            tokens = [dict(row) for row in db.execute("SELECT * FROM auth_tokens")]
    with database_engine("identity").begin() as db:
        for user in users:
            existing = (
                db.execute(
                    text(
                        "SELECT data FROM platform_users WHERE id=:id OR email=:email"
                    ),
                    {"id": user.id, "email": user.email},
                )
                .scalars()
                .all()
            )
            if existing and (len(existing) != 1 or UserInDB(**existing[0]) != user):
                raise ValueError("Conflicting existing identity; no import committed")
            db.execute(
                text(
                    "INSERT INTO platform_users(id,email,data) VALUES (:id,:email,CAST(:data AS jsonb)) ON CONFLICT(id) DO NOTHING"
                ),
                {"id": user.id, "email": user.email, "data": user.model_dump_json()},
            )
        for token in tokens:
            if not db.execute(
                text("SELECT 1 FROM platform_users WHERE id=:id"),
                {"id": token["user_id"]},
            ).scalar():
                raise ValueError(
                    "Session references a missing user; no import committed"
                )
            old = (
                db.execute(text("SELECT * FROM auth_tokens WHERE jti=:jti"), token)
                .mappings()
                .first()
            )
            if old and dict(old) != token:
                raise ValueError("Conflicting session; no import committed")
            columns = [
                "jti",
                "user_id",
                "token_hash",
                "issued_at",
                "expires_at",
                "last_used_at",
                "revoked_at",
            ]
            db.execute(
                text(
                    "INSERT INTO auth_tokens("
                    + ",".join(columns)
                    + ") VALUES ("
                    + ",".join(":" + k for k in columns)
                    + ") ON CONFLICT(jti) DO NOTHING"
                ),
                token,
            )
    return len(users), len(tokens)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--users", required=True)
    parser.add_argument("--tokens")
    args = parser.parse_args()
    users, tokens = import_store(args.users, args.tokens)
    print(
        f"Imported or verified {users} users and {tokens} sessions; source files unchanged"
    )
