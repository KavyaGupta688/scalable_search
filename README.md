# SMSPRSM 2026 - Multimodal Data Platform & Ingestion Engine

Unified multimodal data platform combining production-grade ingestion (S3, NAS SMB/NFS), AI tagging and description enrichment, vector & keyword search, selective forensic download, and cross-cutting audit logging.

## Core Capabilities

1. **Pluggable Data Ingestion (`src/ingestion` / `services/ingestion`):**
   - Connectors for AWS S3, NAS SMB, and NAS NFS.
   - Resilient enumeration with checkpointing.
   - Streaming multipart chunking, MIME verification, and SHA-256 deduplication.
   - Tika metadata extraction and PostgreSQL metadata persistence.
2. **AI Tag & Description Generation (`modules/ai_tag_description_generation`):**
   - Multi-stage GPU pipeline: Object tagging, VLM captioning, OCR parsing, CLIP vector embedding.
   - PII and NSFW safety classification and quality scoring.
3. **Multimodal Search & Discovery — Production Search #2 (`services/search`):**
   - **Hybrid RRF search**: keyword (PostgreSQL full-text) + vector (Qdrant CLIP embeddings) fused via Reciprocal Rank Fusion.
   - Faceted filtering, trending queries, autocomplete suggestions, similar-file discovery.
   - Standalone FastAPI microservice on **port 8002**; proxied from the main server at `/search/*`.
   - See [`services/search/README.md`](services/search/README.md) for full API reference.
4. **Selective Download & Forensic Watermarking (`services/download` / `modules/download_auditing`):**
   - Server-side ZIP bundling of user-selected assets.
   - Steganographic and EXIF cryptographic watermarks with HMAC-SHA256 tokens for leak traceability.
5. **Centralized Enterprise Audit Ledger (`modules/shared/audit.py`):**
   - Append-only immutable relational audit store.
   - Salted IP/device pseudonymization for privacy compliance.
   - Real-time admin activity inspection and streaming CSV export.

---

## Running Locally

```bash
# Install dependencies (platform)
pip install -e .

# Run the unified platform API server (port 8000)
python server.py
# or: uvicorn server:app --reload --port 8000

# Run Production Search Service #2 (port 8002) — in a separate terminal
cd services/search/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

The platform API is at `http://localhost:8000` (docs: `/docs`).  
The search service is at `http://localhost:8002` (docs: `/docs`).  
All `/search/*` calls on port 8000 are transparently proxied to port 8002.

## Running with Docker (Search Service)

```bash
docker compose -f services/search/docker-compose.yml up
```

## Initial Endpoints

- `GET /health`
- `POST /search` — Hybrid RRF search (proxied to port 8002)
- `GET /search/facets`, `GET /search/trending`, `GET /search/suggestions`
- `POST /search/text` — Keyword-only search
- `POST /search/vector` — Vector-only search
- `GET /search/similar/{file_id}` — Similar file search
- `POST /ingestion`, `POST /ingestion/upload`, and `GET /ingestion/{ingestion_id}`
- `POST /ai/enrich`
- `POST /downloads/batch`, `GET /downloads/{download_id}`, and `GET /downloads/audit/events`
- `GET /downloads/audit/export.csv`

---

## Ingestion Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1: Presentation/Access (FastAPI + JWT Auth)              │
│  POST /admin/connectors  |  GET /documents  |  GET /metrics     │
├─────────────────────────────────────────────────────────────────┤
│  Layer 2: Source Interface (Pluggable Connectors)               │
│  S3Connector  |  NASConnectorSMB  |  NASConnectorNFS           │
├─────────────────────────────────────────────────────────────────┤
│  Layer 3: Ingestion Orchestration (Kafka + Checkpointing)       │
│  Enumerator → Kafka ingestion-jobs topic → Worker pool          │
├─────────────────────────────────────────────────────────────────┤
│  Layer 4: Processing & Validation (Streaming Worker)            │
│  Chunk read → MIME validate → SHA-256 hash → MinIO upload       │
├─────────────────────────────────────────────────────────────────┤
│  Layer 5: Storage & Metadata (MinIO + PostgreSQL + Tika)        │
│  Multipart upload → Tika extract → Pydantic normalize → INSERT  │
├─────────────────────────────────────────────────────────────────┤
│  Layer 6: Infrastructure (Docker dev / systemd prod)            │
│  Prometheus + Grafana | ELK Stack | HashiCorp Vault             │
└─────────────────────────────────────────────────────────────────┘
```
