# Data Ingestion

Production-oriented, zero-copy catalogue ingestion for vendor-owned S3, SMB,
and NFS data. Source bytes remain in their existing storage. The system reads
each supported file once to validate its MIME type and calculate SHA-256, reads
the vendor-supplied manifest/sidecar metadata, persists catalogue state in
PostgreSQL, and publishes a Kafka event for
downstream AI processing.

## Hybrid Mode A flow

```text
S3 / SMB / NFS enumeration
        |
        v
Kafka ingestion-jobs
        |
        v
vendor CSV/sidecars -> structured document_metadata
single source read -> MIME -> SHA-256
        |
        +-> PostgreSQL documents (one row per checksum)
        +-> PostgreSQL source_assets (every physical location)
        +-> PostgreSQL document_metadata (one typed row per physical source)
        +-> Kafka ai-processing-events (document + source locator)
```

The binary is not copied or spooled. Small metadata files are bounded by
`METADATA_MAX_FILE_BYTES` and manifests are cached per run/directory.

## Services

- PostgreSQL: catalogue, source locations, checkpoints and current licence state.
- Kafka: ingestion work queue and downstream AI events.
- Vault: S3/SMB connector secrets. Raw credentials never enter PostgreSQL or Kafka.
- Prometheus/Grafana: stage timing, throughput, outcomes and expiry reconciliation.

PostgreSQL may be AWS RDS. S3 and NAS are source systems. There is no MinIO
destination and no second permanent copy.

## Development startup

Create `deploy/docker/.env` from `.env.example`, fill the RDS/Vault settings,
and then run:

```powershell
Set-Location deploy/docker
docker compose up -d kafka vault prometheus grafana ingestion-api
docker compose up -d --scale ingestion-worker=4 ingestion-worker
docker compose up -d retention-reconciler
docker compose run --rm ingestion-api alembic upgrade head
```

The current schema head is `012`.

## Core tables

- `documents`: canonical checksum, size, MIME, preferred source reference and
  entitlement link.
- `document_metadata`: typed vendor metadata from `metadata.csv`, stock-library
  CSV, and per-asset sidecars; one row per physical source, linked to its
  `source_asset` and canonical `document`.
- `source_assets`: every S3/SMB/NFS location, source fingerprint and availability.
- `license_entitlements`: immutable calendar-year licence clock keyed by SHA-256.
- `connectors`: non-secret source configuration and Vault reference.
- `enumeration_checkpoints`: resumable listing state.
- `ingestion_runs`: authoritative per-trigger counters, timings and terminal status.
- `ingestion_run_items`: idempotent per-source outcomes, stage timings and links
  to the resulting document/source asset.

Exact duplicate content creates one `documents` row and multiple
`source_assets` rows. Vendor files are never removed as part of deduplication.

## Direct-source access

Downstream events include `source_asset_id`, connector ID, source reference,
checksum and source fingerprint. Stored credentials are never included.

- `GET /documents/{id}/source` returns a short-lived vendor-S3 presigned URL.
- For SMB/NFS it returns `access_mode=connector_stream`; trusted workers use
  `ingestion.services.source_access.open_source_stream` with Vault credentials.
- `GET /documents/{id}/sources` lists all known locations for failover.

The legacy `/documents/{id}/download` route aliases the new source resolver.

### S3 credential modes

Existing development connectors continue to use `auth_mode=static_keys`; their
keys are stored in Vault and never PostgreSQL. Production connectors should use
`auth_mode=aws_assume_role`, a vendor role ARN and an External ID. The External
ID is stored in Vault. The worker's normal AWS credential chain supplies the
base identity and STS issues refreshable temporary sessions.

Set `SOURCE_ACCESS_ALLOW_STATIC_S3_CREDENTIALS=false` in production after
migration. Short-lived source URLs are capped at both
`SOURCE_ACCESS_PRESIGNED_URL_SECONDS` and the document entitlement expiry.
Expired or inactive entitlements receive HTTP 403 and no URL is generated.
`PATCH /admin/connectors/{connector_id}/s3-auth` replaces an existing
connector's Vault secret and authentication mode, marks it `unverified`, and
requires a successful connector test before its next trigger.

For optional local AssumeRole testing, sign in with the selected AWS CLI or
IAM Identity Center profile, set `AWS_CONFIG_DIR` and `AWS_PROFILE`, then add
the read-only profile override:

```powershell
docker compose `
  -f docker-compose.yml `
  -f docker-compose.override.yml `
  -f docker-compose.aws-dev.yml `
  up -d --build ingestion-api ingestion-worker
```

Do not use this override for the existing `static_keys` development mode.

## Licence expiry

The clock starts after source metadata parsing, hashing, validation and successful
catalogue persistence. Expiry is the same UTC calendar date three years later;
February 29 maps to February 28 in a non-leap target year.

The reconciler marks the entitlement `expired`. It does not delete vendor data
or manage vendor-side revocation. The API independently checks status and expiry
on every source-URL request, so access is denied even before reconciliation has
updated a stale `active` status. Audit history remains the responsibility of the
separate audit module.
Re-ingestion of identical bytes resolves to the existing SHA-256 entitlement,
so it cannot create a fresh licence clock.

## Per-run statistics

`POST /admin/ingestion/trigger/{connector_id}` creates an `ingestion_runs` row
before enumeration starts. Workers upsert one `ingestion_run_items` row per
source reference; Kafka replay therefore cannot double-count a terminal result.

- `GET /admin/ingestion/runs?connector_id=<uuid>` lists recent runs.
- `GET /admin/ingestion/runs/{run_id}` returns exact end-to-end and stage stats.
- `GET /admin/ingestion/runs/{run_id}/items` returns paginated object outcomes.
- `GET /documents/?run_id=<uuid>` returns document metadata created or observed
  in that run.

Prometheus intentionally exposes only bounded aggregate run status/duration
metrics. Structured logs include `run_id`; PostgreSQL is the authoritative
source for per-run history and avoids unbounded Prometheus label cardinality.
Use `scripts/get_ingestion_run.ps1` to save a completed run report.

## Tests

```powershell
python -m pytest -q
python -m ruff check src tests alembic scripts
```

See `METADATA_JOURNEY_GUIDE.md`, `METADATA_TEST_DATASET_GUIDE.md`,
`RETENTION_POLICY_GUIDE.md`, and `PERFORMANCE_AND_SCALE_GUIDE.md` for
operational details.
