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

The current schema head is `011`.

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

## Licence expiry

The clock starts after source metadata parsing, hashing, validation and successful
catalogue persistence. Expiry is the same UTC calendar date three years later;
February 29 maps to February 28 in a non-leap target year.

The reconciler marks the entitlement `expired`. It does not delete vendor data,
manage vendor-side revocation, or store local retention events; audit history is
the responsibility of the separate audit module.
Re-ingestion of identical bytes resolves to the existing SHA-256 entitlement,
so it cannot create a fresh licence clock.

## Tests

```powershell
python -m pytest -q
python -m ruff check src tests alembic scripts
```

See `METADATA_JOURNEY_GUIDE.md`, `METADATA_TEST_DATASET_GUIDE.md`,
`RETENTION_POLICY_GUIDE.md`, and `PERFORMANCE_AND_SCALE_GUIDE.md` for
operational details.
