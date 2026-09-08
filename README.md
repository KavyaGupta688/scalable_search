# SMSPRSM 2026

Runnable foundation for the multimodal file search platform.

## Run locally

```bash
python -m pip install -e .
uvicorn server:app --reload
```

The API is available at `http://localhost:8000`. OpenAPI documentation is at `/docs`.

## AI enrichment development stack

Copy `.env.docker.example` to `.env.docker`, replace its cloud placeholders,
then start Redis, the API, migrations, and a single-concurrency Celery worker:

```bash
cd modules/ai_tag_description_generation
docker compose up --build
```

The Compose file starts a persistent local Redis broker and connects to
externally managed PostgreSQL, Qdrant, and MinIO services. It starts migrations
before the API and worker; the API is available on `localhost:8000`. Check the
queue connection at `GET /ai/health/queue`.

For production, set `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, and
`EVENT_REDIS_URL` to authenticated TLS (`rediss://`) endpoints and use managed
Redis instead of the local Compose service. `REDIS_URL` remains a compatibility
fallback when the three role-specific URLs are not set.

## AI enrichment cloud contract

The enrichment API accepts only a PostgreSQL `file_id`. The ingestion-owned
source table is the authority for the MinIO path, file type, checksum, and
source metadata. Configure its table and column names with the
`SOURCE_*` variables in `modules/ai_tag_description_generation/.env.example`.
The source table must already exist and the AI database user needs `SELECT`
permission on it.

The worker downloads the referenced MinIO object, routes it by modality,
generates metadata asynchronously, then writes to
`document_enrichment_metadata` and upserts a 512-dimensional CLIP vector into
the configured Qdrant collection. Replace all PostgreSQL, Redis, MinIO, and
Qdrant placeholders in `.env.example` with the corresponding cloud endpoints
and credentials before deployment.

## Initial endpoints

- `GET /health`
- `POST /search` and `GET /search/facets`
- `POST /ingestion`, `POST /ingestion/upload`, and `GET /ingestion/{ingestion_id}`
- `POST /ai/enrich`
- `POST /downloads/batch`, `GET /downloads/{download_id}`, and `GET /downloads/audit/events`

The current adapters use in-memory mock data. The ingestion response exposes extraction, AI enrichment, and indexing stages as queued pipeline contracts; database, vector search, storage, SSO/RBAC, and model providers still need production adapters behind the module boundaries documented in [modules/README.md](modules/README.md).

## Prism demo UI

The frontend opens on a demo login and then provides working Library, Search, Datasets, Uploads, Activity, and Profile screens. The Library uses a Pinterest-style masonry stream with preloaded Dogs, Cats, Urban wildlife, and Samsung product sample datasets. Search and dataset browsing work locally so the presentation remains usable without external services.
