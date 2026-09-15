# Production Search Service #2

Standalone **Multimodal Search & Discovery** microservice running on **port 8002**.

## Architecture

```
services/search/
├── backend/          # FastAPI service (Qdrant + PostgreSQL + Redis)
│   ├── app/
│   │   ├── api/routes/     # search, text_search, vector_search, similar_search,
│   │   │                     facets, files, datasets, trending, suggestions, events
│   │   ├── services/       # HybridSearchService (RRF fusion), VectorSearchService...
│   │   ├── repositories/   # FileRepository, DatasetRepository, AnalyticsRepository
│   │   ├── db/             # Postgres (async SQLAlchemy), Qdrant, Redis
│   │   └── core/           # Config, Dependencies, Security
│   └── requirements.txt
└── frontend/         # Standalone search UI (served by backend at /ui)
```

## Key API Endpoints (port 8002)

| Method | Path | Description |
|--------|------|-------------|
| POST | /search | Hybrid RRF search (keyword + vector) |
| POST | /search/text | Keyword / metadata search |
| POST | /search/vector | Vector similarity search |
| GET | /search/similar/{file_id} | Similar file search |
| GET | /search/facets | Facet aggregations |
| GET | /search/trending | Trending queries |
| GET | /search/suggestions | Query autocomplete |
| GET | /files/{file_id} | File metadata & preview |
| GET | /datasets | Popular datasets |
| POST | /events | Log search events |
| GET | /health | Service health check |
| GET | /docs | Interactive API docs (Swagger) |

## Running Locally

```bash
cd services/search/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

## Running with Docker

```bash
# From repo root:
docker compose -f services/search/docker-compose.yml up
```

## Search Modes

- **hybrid** (default): Runs keyword + vector search in parallel, fused via Reciprocal Rank Fusion (RRF)
- **text**: Keyword/metadata-only search (PostgreSQL full-text)
- **vector**: Pure semantic vector search (Qdrant CLIP embeddings)

## Integration with Main Platform

The main platform server (server.py) routes /search/* to this service at port 8002.
