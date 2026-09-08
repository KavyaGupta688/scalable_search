# Multimodal Search Module

Technical implementation of the **Multimodal Search & Discovery Module** for high-volume multimodal asset management.

## Key Features

1. **Hybrid Search (RRF)**: Combines PostgreSQL Full-Text Search (keyword/metadata) and Qdrant (vector similarity) using Reciprocal Rank Fusion ($k=60$).
2. **Semantic / Vector Search**: Natural language query understanding via 512-dim embedding projections.
3. **Similar File Discovery**: Find visual and semantic nearest neighbors for any given file (`POST /search/similar`).
4. **Dynamic Faceted Navigation**: Real-time facet count aggregations across 12 categories, file types, AI-generated flags, PII flags, and date ranges.
5. **Trending Searches**: 24-hour search velocity tracking with query normalization and Redis caching.
6. **Popular Datasets**: 7-day rolling window dataset popularity rankings ($Score = Views_{7d} + 2 \times Downloads_{7d} + 0.5 \times Previews_{7d}$).
7. **Search Autocomplete**: Live suggestions across query history, categories, and AI tags.
8. **File Preview & AI Metadata**: Inspect Vision-Language captions, OCR text, audio speech transcripts, content summaries, and technical specs.
9. **Download & Auditing Integration**: Batch file selection, automated `metadata.csv` bundling, and tamper-evident audit logging.

## API Endpoints

- `POST /search` - Main hybrid search (RRF)
- `GET /search/text?q=...` - Keyword and metadata full-text search
- `POST /search/vector` - Natural language query vector search
- `POST /search/similar` - Find similar files to target `file_id`
- `GET /search/facets` - Dynamic facet aggregations
- `GET /files/{file_id}` - File metadata and preview information
- `GET /datasets/popular` - Dynamically ranked popular datasets
- `GET /search/trending` - Recently popular search queries
- `GET /search/suggestions?q=...` - Autocomplete suggestions
- `POST /events/search` - Record search, click, preview, similar, dataset open events
- `POST /events/export-download` - Dispatch batch selection to Download & Auditing module

## Quickstart

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Seed Database and Qdrant Index
```bash
python seed_data.py
```

### 3. Run Backend API
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive OpenAPI docs will be available at: `http://localhost:8000/docs`

### 4. Run Automated Test Suite
```bash
python -m pytest app/tests/ -v
```

## Production Readiness

The default `.env` (SQLite + embedded Qdrant + in-memory cache fallback) is a
**local development configuration only**. It does not scale to the platform's
target of 500TB+ / millions of files and 3,000+ concurrent users with
sub-second search. Setting `APP_ENV=production` turns on hard guards so the
app fails fast at startup instead of silently running an unsupported
topology in production:

| Guard | Behavior |
|---|---|
| `DATABASE_URL` must be PostgreSQL | Refuses to start on SQLite (no real pooling, no GIN/full-text index, single-writer). |
| `QDRANT_EMBEDDED` must be `False` | Refuses to start with the embedded/local-file Qdrant client, which cannot shard, replicate, or cluster. |
| Qdrant connection failure | Raises `VectorBackendUnavailableException` (503, `VECTOR_BACKEND_UNAVAILABLE`) instead of silently falling back to an empty in-memory vector index that would look like "no results" to users. |
| Redis connection failure | Degrades to a per-process in-memory cache and logs at `ERROR` (alertable) by default (`REDIS_FALLBACK_MEMORY=True`); set to `False` to hard-fail with 503 instead. |
| `SEED_SAMPLE_DATA` | Demo/sample data never auto-loads just because a collection/table is empty - it must be explicitly enabled *and* non-production. |

Required production infrastructure (see `.env.example` for all knobs):

- **PostgreSQL 15+** with `pg_trgm`. On startup, the app creates a weighted
  GIN full-text index (`title`/`category`/`caption`/`content_summary`/
  `description`/`ocr_text`/`transcript`) and a trigram index on `title`.
  Keyword search and facet counts run as SQL (`websearch_to_tsquery` +
  `ts_rank_cd`, `GROUP BY ... COUNT(*)`) - nothing is loaded into Python and
  scored/aggregated by hand, which is what let the old implementation blow up
  past a few thousand rows.
- **Qdrant server/cluster** (not embedded), sized per the capacity-planning
  numbers for your expected file count. `shard_number`/`replication_factor`
  are fixed at collection-creation time - decide them (`QDRANT_SHARD_NUMBER`,
  `QDRANT_REPLICATION_FACTOR`) before the first production ingest. Payload
  indexes for every filterable field (`file_type`, `category`, `dataset_id`,
  `pii_detected`, `nsfw_detected`, `ai_generated`, `source_batch`, `file_id`)
  are created automatically on startup.
- **Redis 7+** as a real shared cache tier across app replicas.
- Check `GET /readyz` for a liveness-vs-readiness split suitable for a load
  balancer or Kubernetes probe - it actually pings Postgres and Qdrant,
  unlike `/health`/`/livez` which only confirm the process is up.
- `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` size the app's Postgres connection pool;
  put PgBouncer in front once replica count grows so
  `(pool_size + max_overflow) * replicas` doesn't exceed Postgres's
  `max_connections`.
