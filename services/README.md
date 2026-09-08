# Integrated services

The `integration` branch preserves each team branch as a separately deployable service:

- `services/ingestion` — connectors, enumeration, validation, MinIO/Kafka pipeline.
- `services/search` — hybrid keyword/vector search, facets, previews, and event APIs.
- `services/download` — S3 streaming, batch downloads, watermarking, and forensic audit.

All services must point at the same PostgreSQL database using `DATABASE_URL` / `DATABASE_URL_SYNC`.
Use separate PostgreSQL schemas (`ingestion`, `search`, `enrichment`, and `audit`) so ownership
and migrations remain isolated while joins and reporting can still use one database.

Redis is the shared cache and Celery broker. Qdrant remains the vector index; it is not a second
relational database. S3/NAS is the source-of-truth object storage.

## Current integration status

The source branches are merged/imported, but the service-specific settings and migrations still
need to be consolidated behind the shared environment contract. The root `server.py` remains the
platform shell; service processes can be started independently until the gateway wiring is
completed.
