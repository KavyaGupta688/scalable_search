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
then start Redis, migrations, the API, a Celery worker, and the ingestion Kafka consumer:

```bash
cd modules/ai_tag_description_generation
docker compose up --build
```

The Compose file starts a persistent local Redis broker and connects to
externally managed PostgreSQL, Qdrant, Kafka, and ingestion API services. It starts migrations
before the API and worker; the API is available on `localhost:8000`. Check the
queue connection at `GET /ai/health/queue`.

For production, set `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, and
`EVENT_REDIS_URL` to authenticated TLS (`rediss://`) endpoints and use managed
Redis instead of the local Compose service. `REDIS_URL` remains a compatibility
fallback when the three role-specific URLs are not set.

## AI enrichment cloud contract

The preferred trigger is ingestion's `ai-processing-events` Kafka topic. The
AI module uses the canonical `document_id`, requests a short-lived S3 URL or
NAS stream from ingestion immediately before processing, verifies size and
SHA-256, and never stores source credentials. Generated metadata is written to
`document_enrichment_metadata` without modifying vendor metadata, and a
512-dimensional CLIP vector is upserted to Qdrant. The manual compatibility
endpoint accepts `{"document_id": "..."}`.

## Initial endpoints

- `GET /health`
- `POST /search` and `GET /search/facets`
- `POST /ingestion`, `POST /ingestion/upload`, and `GET /ingestion/{ingestion_id}`
- `POST /ai/enrich`
- `POST /downloads/batch`, `GET /downloads/{download_id}`, and `GET /downloads/audit/events`

The current adapters use in-memory mock data. The ingestion response exposes extraction, AI enrichment, and indexing stages as queued pipeline contracts; database, vector search, storage, SSO/RBAC, and model providers still need production adapters behind the module boundaries documented in [modules/README.md](modules/README.md).

## Prism demo UI

The frontend opens on a demo login and then provides working Library, Search, Datasets, Uploads, Activity, and Profile screens. The Library uses a Pinterest-style masonry stream with preloaded Dogs, Cats, Urban wildlife, and Samsung product sample datasets. Search and dataset browsing work locally so the presentation remains usable without external services.
