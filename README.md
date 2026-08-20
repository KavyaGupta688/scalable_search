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

The current adapters use in-memory mock data. The ingestion response exposes extraction, AI enrichment, and indexing stages as queued pipeline contracts; database, vector search, storage, SSO/RBAC, and model providers still need production adapters behind the module boundaries documented in [modules/README.md](modules/README.md).