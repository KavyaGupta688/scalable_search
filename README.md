# Data Ingestion Module

Production-grade multimodal data ingestion system for AI processing pipelines. Collects, validates, deduplicates, stores, and tags datasets (100TB–500TB scale) from S3-compatible buckets and on-premises NAS shares (SMB/NFS).

## Architecture

Six-layer architecture matching the reference design:

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

## Quick Start (Development)

### Prerequisites
- Docker & Docker Compose v2+
- Git

### 1. Clone and start the dev stack

```bash
cd deploy/docker
docker compose up -d
```

This starts **all infrastructure** (PostgreSQL, MinIO, Kafka, Vault, Tika, Elasticsearch, Logstash, Kibana, Prometheus, Grafana) plus the application services (API, Worker).

The `docker-compose.override.yml` is auto-loaded, exposing these ports:

| Service       | Port(s)        | URL                          |
|--------------|----------------|------------------------------|
| API Server   | 8000           | http://localhost:8000        |
| MinIO Console| 9000, 9001     | http://localhost:9001        |
| PostgreSQL   | 5432           | localhost:5432               |
| Kafka        | 9092           | localhost:9092               |
| Vault        | 8200           | http://localhost:8200        |
| Grafana      | 3000           | http://localhost:3000        |
| Kibana       | 5601           | http://localhost:5601        |
| Prometheus   | 9090           | http://localhost:9090        |

### 2. Get an API token (dev mode)

```bash
curl -X POST http://localhost:8000/auth/token \
  -d "username=admin&password=dev"
```

Response:
```json
{"access_token": "eyJhbG...", "token_type": "bearer", "expires_in": 3600}
```

### 3. Create a connector

```bash
# S3 connector
```curl -X POST http://localhost:8000/admin/connectors/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "vendor-bucket",
    "source_type": "S3",
    "s3": {
      "endpoint_url": "http://minio:9000",
      "bucket": "source-data",
      "access_key": "minioadmin",
      "secret_key": "minioadmin",
      "addressing_style": "path",
      "signature_version": "s3v4"
    }
  }'
```

### 4. Test the connector

```bash
curl -X POST http://localhost:8000/admin/connectors/<id>/test \
  -H "Authorization: Bearer <token>"
```

### 5. Trigger enumeration

```bash
curl -X POST http://localhost:8000/admin/ingestion/trigger/<connector_id> \
  -H "Authorization: Bearer <token>"
```

Or run the enumerator directly:
```bash
docker compose run --rm ingestion-enumerator python scripts/run_enumerator.py <connector_id>
```

### 6. Monitor

- **API docs**: http://localhost:8000/docs (Swagger UI)
- **Metrics**: http://localhost:8000/metrics (Prometheus format)
- **Grafana**: http://localhost:3000 (pre-configured dashboard)
- **Kibana**: http://localhost:5601 (structured JSON logs)
- **Health**: http://localhost:8000/health

---

## Production Deployment (Bare Metal + systemd)

> **Dev uses Docker Compose. Production uses bare metal + systemd. These are NOT the same deployment path.**

### Prerequisites (bare metal Linux)
- Python 3.11+
- PostgreSQL 16+
- MinIO (standalone or distributed)
- Apache Kafka (KRaft mode)
- HashiCorp Vault (Community Edition)
- Apache Tika Server
- Elasticsearch + Logstash + Kibana
- Prometheus + Grafana

### Install the application

```bash
sudo bash deploy/install/setup-production.sh
```

This script:
1. Creates `ingestion` user/group
2. Installs system dependencies (`libmagic1`, Python 3.11)
3. Creates virtualenv at `/opt/ingestion/venv`
4. Installs the Python package
5. Generates `/etc/ingestion/ingestion.env` template
6. Copies systemd unit files to `/etc/systemd/system/`
7. Enables and starts services

### Configure

Edit `/etc/ingestion/ingestion.env` with your production values:

```bash
# Database
DB_HOST=db.internal
DB_PORT=5432
DB_NAME=ingestion
DB_USER=ingestion
DB_PASSWORD=<from-vault>

# MinIO
MINIO_ENDPOINT_URL=https://minio.internal:9000
MINIO_ACCESS_KEY=<from-vault>
MINIO_SECRET_KEY=<from-vault>
MINIO_BUCKET=ingestion-data

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka1.internal:9092,kafka2.internal:9092

# Vault
VAULT_URL=https://vault.internal:8200
VAULT_AUTH_METHOD=approle
VAULT_ROLE_ID=<role-id>
VAULT_SECRET_ID=<secret-id>

# JWT (production: tokens come from your SSO/IdP)
JWT_SECRET_KEY=<strong-random-secret>
JWT_DEV_TOKEN_ENABLED=false

# Environment
APP_ENVIRONMENT=production
```

### Manage services

```bash
# Start/stop/restart
sudo systemctl start ingestion-api
sudo systemctl start ingestion-worker

# View logs
journalctl -u ingestion-api -f
journalctl -u ingestion-worker -f

# Enable reconciliation timer
sudo systemctl enable --now ingestion-reconciliation.timer
```

### Backup & Disaster Recovery

> **The database should be backed up using the organization's existing backup infrastructure.**
>
> Recommended: Configure PostgreSQL continuous archiving (WAL) or periodic `pg_dump` via your DBA team. MinIO supports bucket replication for object storage redundancy. Kafka topic retention handles message replay.
>
> Specific backup automation will be added based on client infrastructure feedback.

---

## Project Structure

```
data-ingestion/
├── src/ingestion/
│   ├── config.py                  # Pydantic Settings (all env-based)
│   ├── main.py                    # FastAPI app factory
│   ├── api/                       # Layer 1: REST API + JWT auth
│   ├── connectors/                # Layer 2: S3, SMB, NFS connectors
│   ├── orchestration/             # Layer 3: Enumeration + checkpointing
│   ├── worker/                    # Layer 4: Streaming processor
│   ├── storage/                   # Layer 5: MinIO + metadata pipeline
│   ├── models/                    # SQLAlchemy ORM models
│   ├── schemas/                   # Pydantic request/response schemas
│   ├── services/                  # Vault, Kafka, Database
│   ├── monitoring/                # Prometheus metrics + JSON logging
│   └── reconciliation/            # Gap detection + re-drive
├── scripts/                       # Entrypoints (API, worker, enumerator)
├── deploy/
│   ├── docker/                    # Docker Compose (dev only)
│   ├── systemd/                   # systemd units (production)
│   ├── install/                   # Bare-metal install script
│   └── grafana/                   # Dashboard JSON
├── migrations/                    # Raw SQL migrations
├── alembic/                       # Alembic migrations
└── tests/                         # Test scaffold
```

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Kafka library | `confluent-kafka` | librdkafka wrapper, 10x faster than kafka-python, actively maintained |
| UUIDv7 | `uuid-utils` | Rust-based, RFC 9562, 10-20x faster than uuid6 |
| SMB access | `smbprotocol` | SDK-based, no OS mount, works in unprivileged containers |
| JWT signing | HS256 | Simpler key management; RS256 available if org needs asymmetric |
| Tika | Server sidecar | `TIKA_CLIENT_ONLY=True` prevents 80MB JAR auto-download |
| NFS | OS-mount fallback | Pure SDK NFS in Python is poorly maintained |

## Security

- **No secrets in code or database**: All credentials stored in HashiCorp Vault; Postgres only holds vault path references
- **JWT-based auth**: Permission claims (`ingestion:configure`, `data:read`, `data:download`, `ingestion:trigger`)
- **Token issuance**: Dev-only (`JWT_DEV_TOKEN_ENABLED=true`); production uses organization SSO
- **Connector model invariant**: The `Connector` ORM model has zero columns for raw credentials

## Streaming Pipeline (Zero Full-Object Buffering)

Every file, regardless of size, is processed in a single streaming pass:

```
Source → 8MB chunks → [First chunk: MIME validate] → SHA-256 update → MinIO upload_part
                                                                            ↓
                                                          After last chunk: hash complete
                                                                            ↓
                                                    Dedup check → complete/abort multipart
                                                                            ↓
                                                        Metadata pipeline → DB INSERT
```

No file is ever fully buffered in memory or on local disk.

## License

Proprietary — see LICENSE file.

## Licensed-content retention

Successfully ingested MinIO content has a database-audited calendar-year
expiry and optional automatic lifecycle/reconciliation enforcement. Read
[`RETENTION_POLICY_GUIDE.md`](RETENTION_POLICY_GUIDE.md) before enabling any
deletion capability.
