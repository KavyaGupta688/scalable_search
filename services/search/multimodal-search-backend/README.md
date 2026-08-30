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
