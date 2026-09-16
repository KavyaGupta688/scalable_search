# SMSPRSM 2026

Runnable foundation for the multimodal file search platform.

## Run locally

```bash
python -m pip install -e .
uvicorn server:app --reload
```

The API is available at `http://localhost:8000`. OpenAPI documentation is at `/docs`.

## Initial endpoints

- `GET /health`
- `POST /search` and `GET /search/facets`
- `POST /ingestion`, `POST /ingestion/upload`, and `GET /ingestion/{ingestion_id}`
- `POST /ai/enrich`
- `POST /downloads/batch`, `GET /downloads/{download_id}`, and `GET /downloads/audit/events`

The current content adapters use in-memory mock data. The ingestion response exposes extraction, AI enrichment, and indexing stages as queued pipeline contracts; vector search, storage, SSO, and model providers still need production adapters behind the module boundaries documented in [modules/README.md](modules/README.md).

## Authentication

The initial local accounts are:

- Administrator: `admin@platform.internal` / `admin123`
- Standard user: `user@platform.internal` / `user123`

Change these credentials before deploying outside a local development environment. Passwords are bcrypt-hashed in `data/users.json`.

Successful login returns a signed JWT and creates an active session in `data/auth.db`, table `auth_tokens`. Only a SHA-256 fingerprint of the JWT is stored, never the reusable bearer token itself. Every authenticated request, including all ingestion endpoints, must present the JWT and pass both signature validation and the database-session check.

To confirm the current browser token is stored, call `GET /auth/token-status` with the `Authorization: Bearer <token>` header. A valid response includes `"stored": true` and the session's JWT ID (`jti`). To inspect the database directly from the project directory:

```powershell
python -c "import sqlite3; db=sqlite3.connect('data/auth.db'); print(db.execute('SELECT jti,user_id,issued_at,expires_at,last_used_at,revoked_at FROM auth_tokens').fetchall())"
```

The frontend provides credential-based sign-in only. There are no one-click or auto-filled login paths.
