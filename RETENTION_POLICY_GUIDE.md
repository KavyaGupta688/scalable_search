# Three-year retention: Option A rollout

This deployment uses an **unversioned MinIO bucket**, no legal holds, and a
nullable `object_version_id` reserved for a later production decision. The
retention service fails closed if it finds an Enabled or Suspended bucket.

## Contract and immutable clock

The immutable development licence identity is `sha256:<content checksum>`.
Consequently, identical bytes resolve to the same licence clock even if an
administrator creates another connector, changes the bucket, or renames the
source object. Migration `008` converts existing connector/path identities to
this checksum identity and refuses to complete if any historical entitlement
cannot be mapped safely.

This closes the connector/path loophole for byte-identical re-ingestion. A file
whose bytes are deliberately changed has a different checksum, so production
should use the client's contract-backed vendor asset or entitlement ID when
that authoritative identifier becomes available. Connector administration and
licence-renewal approval should also be separate permissions in production.

The first successful ingestion creates one immutable `license_entitlements`
row. Its `license_start_at` is the UTC time after the final MinIO write and
metadata processing succeed. `expires_at` is the same UTC calendar date and
time three years later. February 29 maps to February 28 in a non-leap target
year. Re-uploading or replacing data cannot update this clock. An expired or
revoked entitlement rejects re-ingestion until a separately approved renewal
revision exists.

Migrations `004` through `008` normalize retention and enforce the content-based
licence identity. The document fields are:

- `source_connector_id`, `source_ref`, `entitlement_id`
- `bucket_name`, `storage_path`, nullable `object_version_id`
- `retention_status`, `deleted_at`, and `last_reconciled_at`

Licence start, expiry, policy, renewal, and approval exist only in
`license_entitlements`. Deletion method and error details exist only in
append-only `retention_events`. Migration `005` also drops the unrelated
`forensic_audit_logs` table. Database
triggers reject hard deletion of all three audit record types, reject updates
to entitlement clocks, and protect the document-to-entitlement identity.
Database-owner access must still be restricted and externally audited.

## Enforcement

At the linked entitlement's `expires_at`, the API stops issuing download URLs. The continuous
reconciler deletes the unversioned object, verifies absence, changes the
document to `deleted_by_reconciler`, expires the entitlement, and appends a
retention event. Metadata remains as a tombstone.

MinIO lifecycle is a secondary whole-day fail-safe. The managed object rule
expires current objects after 1,097 days and aborts incomplete multipart
uploads after seven days. The extra day ensures MinIO's object timestamp cannot
cause deletion before the exact three-calendar-year database deadline.

Object tags are off by default to avoid an additional request per ingested
object. PostgreSQL is authoritative.

## Configuration

Add these non-secret settings to `deploy/docker/.env`:

```dotenv
RETENTION_ENABLED=true
RETENTION_DRY_RUN=true
RETENTION_EXPECTED_BUCKET_VERSIONING=Unversioned
RETENTION_WRITE_OBJECT_TAGS=false
RETENTION_POLICY_YEARS=3
RETENTION_OBJECT_PREFIX=
RETENTION_LIFECYCLE_RULE_ID=ingestion-retention-v1
RETENTION_LIFECYCLE_EXPIRATION_DAYS=1097
RETENTION_NONCURRENT_EXPIRATION_DAYS=1097
RETENTION_INCOMPLETE_MULTIPART_DAYS=7
RETENTION_RECONCILIATION_INTERVAL_SECONDS=900
RETENTION_RECONCILIATION_BATCH_SIZE=500
RETENTION_METRICS_PORT=9200
```

An empty prefix governs the entire configured ingestion bucket. Prefer a
dedicated bucket. Do not enable enforcement on a bucket containing unrelated
objects.

## Development setup and dry-run

MinIO uses port 9002 for the S3 API in this development installation; port
9003 is only the console. In a PowerShell session containing the root variables
without displaying their values:

```powershell
cd C:\Users\hrbrv\minio
.\mc.exe alias set retention-local `
  "http://127.0.0.1:9002" `
  $env:MINIO_ROOT_USER `
  $env:MINIO_ROOT_PASSWORD

.\mc.exe ready retention-local
.\mc.exe version info "retention-local/$env:MINIO_BUCKET"
```

Do not continue if the result is Enabled or Suspended. A previously versioned
bucket requires an inventory and cleanup decision because suspending versioning
does not remove old versions.

Apply migrations from the repository root:

```powershell
cd C:\Users\hrbrv\.gemini\antigravity\scratch\data-ingestion
py -m alembic upgrade head
py -m alembic current
```

Expected revision: `008`.

Build and start the development services. PostgreSQL and MinIO remain external:

```powershell
cd deploy\docker
docker compose build ingestion-api ingestion-worker retention-reconciler
docker compose up -d kafka vault tika prometheus grafana ingestion-api ingestion-worker
docker compose ps
```

Run one non-destructive retention audit:

```powershell
docker compose run --rm retention-reconciler `
  python scripts/run_retention.py --once
```

Dry-run must report the proposed lifecycle rule and due counts without
installing rules or deleting objects.

## Safe end-to-end deletion fixture

Use an existing connector UUID. It is needed only to satisfy the source audit
foreign key. Create one uniquely named, already-expired fixture; the script is
forbidden in production and refuses a versioned bucket:

```powershell
$connectorId = "REPLACE-WITH-AN-EXISTING-CONNECTOR-UUID"

docker compose run --rm retention-reconciler `
  python scripts/seed_retention_fixture.py --connector-id $connectorId
```

Save the printed `fixture_document_id` and `fixture_object_key`. Confirm the
object initially exists in MinIO and the document/entitlement exist in RDS.

Keep `RETENTION_DRY_RUN=true` and run the reconciler once. Expected: the object
still exists and `dry_run_due=1` (or higher if other due data exists).

After verifying the fixture and ensuring no real rows are unexpectedly due,
set `RETENTION_DRY_RUN=false` and run once:

```powershell
docker compose run --rm retention-reconciler `
  python scripts/run_retention.py --once
```

Expected:

- the fixture key is absent from MinIO;
- the document row remains with `retention_status='deleted_by_reconciler'`;
- `deleted_at` is populated;
- its entitlement is `expired`;
- one `retention_events` row records `deleted_by_reconciler`, which is the
  deletion method/outcome.

Install the lifecycle rule only after this controlled test succeeds:

```powershell
docker compose run --rm retention-reconciler `
  python scripts/run_retention.py --apply-only

C:\Users\hrbrv\minio\mc.exe ilm rule ls `
  "retention-local/$env:MINIO_BUCKET" --json
```

Expected managed ID: `ingestion-retention-v1-objects`. Option A must not create
a version/delete-marker rule.

Start continuous enforcement:

```powershell
docker compose up -d retention-reconciler prometheus grafana
docker compose ps retention-reconciler
docker compose logs retention-reconciler --tail=200
```

## Audit queries

```sql
SELECT retention_status, count(*)
FROM documents
GROUP BY retention_status
ORDER BY retention_status;

SELECT d.id, d.bucket_name, d.storage_path, e.license_start_at,
       e.expires_at, d.retention_status, d.deleted_at
FROM documents AS d
JOIN license_entitlements AS e ON e.id = d.entitlement_id
WHERE e.expires_at <= now()
ORDER BY e.expires_at;

SELECT license_subject_id, license_start_at, expires_at, status, revision
FROM license_entitlements
ORDER BY created_at DESC;

SELECT document_id, event_type, outcome, event_at, actor_type, details
FROM retention_events
ORDER BY event_at DESC;
```

## Monitoring and alerts

Prometheus must show `retention-reconciler:9200` as UP. Monitor:

- `ingestion_retention_expired_pending` — expected zero after the deletion SLO
- `ingestion_retention_active_missing` — expected zero
- `ingestion_retention_lifecycle_configured` — expected one after apply
- `ingestion_retention_reconciliation_runs_total{outcome="failure"}`
- `ingestion_retention_last_success_timestamp_seconds`
- MinIO `minio_ilm_expiry_missed_tasks` when its authenticated metrics are added

Supplied alert rules cover lifecycle application failure, reconciliation
failure, expired-but-not-deleted content, premature disappearance, stale
reconciliation, and MinIO ILM backlog.

## Existing objects and rollback

Migration `004` creates a development entitlement from each existing
connector/source reference and uses the earlier successful-ingestion timestamp.
It refuses to migrate legacy documents lacking a connector rather than guessing
their identity. Review all backfilled dates in dry-run before deletion.

To pause deletion, set `RETENTION_ENABLED=false` and stop the reconciler. An
installed MinIO lifecycle rule continues independently and must be removed
during an approved rollback before any object reaches its lifecycle age.
Already deleted content is irreversible and must not be restored after expiry.
