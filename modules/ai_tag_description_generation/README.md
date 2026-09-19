# AI tag and description generation

This service consumes canonical document events from ingestion, obtains source
bytes through ingestion's entitlement-checked access API, runs the multimodal
pipeline, stores AI-owned metadata in PostgreSQL, and upserts 512-dimensional
CLIP embeddings to Qdrant. It does not receive vendor S3/NAS credentials and
does not copy source assets into intermediate object storage.

## Integration contract

The primary trigger is the `ai-processing-events` Kafka topic. Each event must
include `run_id`, `document_id`, `source_asset_id`, validated MIME type, size,
SHA-256, source provenance, entitlement ID/timestamps, and the vendor metadata
snapshot. The consumer group is AI-owned and delivery is treated as
at-least-once.

Before inference the worker calls `GET /documents/{document_id}/source`:

- S3 sources return a short-lived presigned URL.
- SMB/NFS sources return `connector_stream`; the worker then calls the
  configured `/documents/{document_id}/content` ingestion proxy.
- The downloaded size and SHA-256 must match the ingestion event.
- URLs, source credentials, and secrets are never stored or logged.

The NAS content route is an ingestion-module dependency described in the
handoff. NAS processing will fail closed until that authenticated streaming
route is deployed. S3 processing works with the existing presigned-URL route.

Vendor `document_metadata.tags` remain vendor-owned. AI output is written to
`document_enrichment_metadata` under the idempotent key
`(document_id, model_name, model_version, enrichment_version)`.

## Required configuration

Copy `.env.example` to `.env` for host execution or `.env.docker.example` to
`.env.docker` for Compose. Configure:

- PostgreSQL URLs with TLS and permission to create/update AI-owned tables.
- `INGESTION_API_BASE_URL` and a short-lived service token with `data:read` and
  `data:download`.
- Kafka bootstrap/security settings, topic, DLQ topic, and consumer group.
- Redis URLs for Celery and enrichment result events.
- Qdrant URL, API key, collection name, cosine distance, and vector size 512.
- Model checkpoints and model-cache storage.

Do not configure vendor S3 keys, NAS passwords, Vault tokens, or presigned URLs
in this module.

## Database migration

Run from the repository root:

```powershell
alembic -c modules/ai_tag_description_generation/alembic.ini upgrade head --sql
alembic -c modules/ai_tag_description_generation/alembic.ini upgrade head
```

Revision `003_ingestion_zero_copy` replaces legacy file/storage fields with
`document_id`, run/source/entitlement provenance, canonical MIME/size/checksum,
and bounded vendor metadata. The AI migration ledger remains separate from the
ingestion module's Alembic history.

## Validation and startup

```powershell
python modules/ai_tag_description_generation/scripts/check_cloud_connections.py
python modules/ai_tag_description_generation/scripts/check_database_schema.py
python -m unittest discover -s modules/ai_tag_description_generation/tests -v
docker compose --env-file modules/ai_tag_description_generation/.env.docker `
  -f modules/ai_tag_description_generation/docker-compose.yml up --build
```

Compose starts migrations, the AI API, a manual/retry Celery worker, the Kafka
consumer, and Redis. PostgreSQL, ingestion API, Kafka, and Qdrant are external
shared services and must be reachable from the containers.

The manual compatibility endpoint is `POST /ai/enrich` with
`{"document_id": "..."}`. Kafka remains the preferred production trigger.

## Processing behavior

Files are streamed into an operating-system temporary file only for the life
of a processing attempt and are deleted in a `finally` block. Vendor metadata
is used as bounded, untrusted model context and remains distinct from generated
tags. PostgreSQL is the result source of truth; Kafka offsets are committed
only after the AI result has reached a terminal persisted state.

Fine-grained CLIP labels live in
`worker/pipeline/fine_grained_taxonomy.py`. The database-free OCR demo remains
available through `scripts/run_demo.ps1`; it intentionally bypasses ingestion,
PostgreSQL, Kafka, and Qdrant while exercising Redis/Celery and local models.
