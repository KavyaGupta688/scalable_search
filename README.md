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
3. **Multimodal Search & Discovery (`services/search` / `modules/searching`):**
   - Hybrid semantic (Qdrant) + BM25 keyword search (PostgreSQL).
   - Faceted filtering (type, resolution, date, category).
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
# Install dependencies
pip install -e .

# Run the unified platform API server
python server.py
# or: uvicorn server:app --reload --port 8000
```

The API is available at `http://localhost:8000`. OpenAPI documentation is at `/docs`.

## Initial Endpoints

- `GET /health`
- `POST /search` and `GET /search/facets`
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
