# Enumeration performance and scale guide

## Staged capacity qualification: 10 GB to 1 TiB

Do not run stages concurrently. Each stage must use a connector prefix whose
objects have not already been ingested; otherwise checksum deduplication turns
the run into a duplicate benchmark. Start with four worker replicas and the
existing 12-partition job topic. The worker remains sequential within each
process so Kafka offset ordering stays simple and correct.

Before every stage, confirm the exact prefix byte/object totals, zero consumer
lag and healthy Prometheus targets. Migration `012` persists the trigger in
`ingestion_runs` and every source outcome in `ingestion_run_items`; retry counts
and transferred bytes include failed attempts, while stage timings describe the
terminal attempt without adding a shared hot-row write. Use
`scripts/get_ingestion_run.ps1` after completion for
the authoritative JSON report. Prometheus remains an aggregate operational
view and structured logs carry the same `run_id` for investigation.

| Stage | Proceed only when |
| --- | --- |
| 10 GB | No data loss; zero unresolved failures; at least 6 MiB/s for a sub-48-hour 1-TiB projection |
| 50 GB | Throughput is at least 80% of the 10-GB result; queue lag drains and source access remains healthy |
| 100 GB | No growing memory/disk pressure; no RDS connection exhaustion; projected duration is acceptable |
| 1 TiB | Vendor-source capacity is confirmed; prior stage is stable; AWS egress and runtime budget approved |

For a 12-hour 1-TiB target, sustained end-to-end throughput must be about
24.3 MiB/s. For 24 hours it must be about 12.1 MiB/s; for 48 hours, about
6.1 MiB/s. If the 10-GB stage is below 6 MiB/s, do not increase dataset size:
move workers closer to S3 or resolve the dominant measured stage.

## What was slow

The former S3 implementation called `list(paginator.paginate(...))`.  It made
every `ListObjectsV2` request and stored every response before publishing the
first Kafka job.  With a bucket containing many small images, first-job
latency was therefore the time to list the *entire* scope and memory grew with
the number of pages.

The implementation now requests and publishes one page at a time.  A page has
at most 1,000 object records, so first-job latency is one S3 list request and
enumerator memory is `O(page_size)`, not `O(total objects)`.

## Safe 3 GB benchmark procedure

Do this with a non-empty S3 prefix that contains only the 3 GB test dataset.
Do not benchmark with an empty prefix: that means the whole bucket.

For a true end-to-end measurement, use a test dataset that has not already
produced `documents` rows. Replaying a partially processed run is correct and
safe, but destination-exists and checksum-dedup paths will intentionally skip
work and invalidate a fresh-throughput comparison. Use a separate test-only
source prefix if needed; do not delete existing RDS catalogue data just to make
a benchmark look clean.

1. Apply migration `012` to RDS using your existing global Alembic setup, then
   rebuild the two changed images:

   ```powershell
   cd C:\Users\hrbrv\.gemini\antigravity\scratch\data-ingestion
   alembic upgrade head
   cd deploy\docker
   docker compose build ingestion-api ingestion-worker
   docker compose up -d --force-recreate ingestion-api ingestion-worker
   ```

   To make the local test use more than one worker, ensure the job topic has
   multiple partitions. This operation only increases partitions; it does not
   remove messages. Then start four worker replicas. (The code is deliberately
   sequential inside each worker, so this is the safe way to parallelise it.)

   ```powershell
   docker compose exec kafka kafka-topics --bootstrap-server kafka:29092 `
     --alter --topic ingestion-jobs --partitions 12
   docker compose up -d --scale ingestion-worker=4 ingestion-worker
   ```

2. Obtain a fresh API token, then apply the test scope to the already verified
   connector.  Set `max_objects` to `$null` only after confirming that the
   prefix contains exactly the test dataset.  Keep `page_size` at `1000`.

   ```powershell
   $headers = @{ Authorization = "Bearer $token" }
   $scope = @{
     prefix = "your-test-dataset-prefix/"
     max_objects = $null
     page_size = 1000
   } | ConvertTo-Json

   Invoke-RestMethod -Method Patch `
     -Uri "http://localhost:8000/admin/connectors/$connectorId/s3-scope" `
     -Headers $headers -ContentType "application/json" -Body $scope
   ```

   For a small dry run first, use `max_objects = 1000`.  A cap deliberately
   processes the first N keys in the prefix and then finishes; it does not
   silently claim that the remaining keys were ingested.

3. Start both services and trigger one enumeration. If `ingestion-jobs`
   already contains old test work, use a new job topic by setting
   `KAFKA_INGESTION_TOPIC=ingestion-jobs-3gb-benchmark` in `deploy/docker/.env`,
   then recreate API and workers and create that topic with the same 12
   partitions:

   ```powershell
   docker compose exec kafka kafka-topics --bootstrap-server kafka:29092 `
     --create --if-not-exists --topic ingestion-jobs-3gb-benchmark `
     --partitions 12 --replication-factor 1
   ```

   For a clean full-scope run, explicitly reset the connector's
   checkpoint first. Do **not** erase RDS catalogue data to benchmark.

   ```powershell
   docker compose up -d ingestion-api ingestion-worker
   $started = Get-Date
   Invoke-RestMethod -Method Post `
     -Uri "http://localhost:8000/admin/ingestion/reset-checkpoint/$connectorId" `
     -Headers $headers
   Invoke-RestMethod -Method Post `
     -Uri "http://localhost:8000/admin/ingestion/trigger/$connectorId" `
     -Headers $headers
   ```

4. The enumeration is complete when the API log contains `Enumeration
   completed`.  The JSON `context` includes `files_enumerated`, S3
   `list_seconds`, first-page latency, and peak RSS.  The pipeline is complete
   only when Kafka group lag reaches zero:

   ```powershell
   docker compose logs ingestion-api --tail=200
   docker compose exec kafka kafka-consumer-groups `
     --bootstrap-server kafka:29092 --describe --group ingestion-workers
   ```

5. Scrape metrics after completion.  Histogram `_sum` is cumulative seconds;
   `_count` is the number of samples.  Divide sum by count for mean per object.

   ```powershell
   Invoke-WebRequest http://localhost:8000/metrics | Select-Object -Expand Content |
     Select-String 'ingestion_(enumeration|processing|process_memory)'

   docker compose exec ingestion-worker python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:9100/metrics').read().decode())" |
     Select-String 'ingestion_(processing|throughput|files)'

   "End-to-end seconds: $(((Get-Date) - $started).TotalSeconds)"
   ```

## Timing mapping

| Required timing | Metric / source |
| --- | --- |
| Enumeration list requests | API: `stage="enumeration_list_page"`; final log `list_seconds` |
| Full enumeration (listing + Kafka publishing/checkpoints) | API: `stage="enumeration_total"` |
| Source object download/read | Worker: `stage="source_read"` |
| SHA-256 hashing | Worker: `stage="hashing"` |
| MIME validation | Worker: `stage="validation"` |
| Vendor metadata reads | Worker: `stage="source_metadata"` |
| PostgreSQL reads/writes | Worker: `stage="postgresql_read"`, `stage="postgresql_write"`, and `stage="postgresql_commit"` |
| Per-object total | Worker: `stage="total"` |
| End-to-end total | Wall clock from trigger until Kafka lag is zero |
| Enumerator memory | API: `ingestion_process_memory_peak_bytes` |

## Benchmark report template

Record one cold run of the old implementation (if practical) and one run of
this build against the same prefix, credentials, and RDS. Do not
compare a capped run with an uncapped run.

| Measure | Before | After |
| --- | ---: | ---: |
| Object count | | |
| Dataset bytes | | |
| First job latency | all-listing time | one list-page time |
| Enumeration list seconds | | |
| Enumeration total seconds | | |
| Source-read seconds (sum) | | |
| Hashing seconds (sum) | | |
| Validation seconds (sum) | | |
| Source-metadata seconds (sum) | | |
| PostgreSQL-write seconds (sum) | | |
| End-to-end seconds | | |
| Objects/sec | | |
| MiB/sec | | |
| Enumerator peak RSS | grows with object count | bounded by one page plus process overhead |

## Production path for 450 TB

The streaming paginator, batched Kafka durability checkpoint, 1,000-key pages,
connection reuse, bounded memory, and cached bounded manifest reads
are production changes.  The prefix and `max_objects` controls are test
scoping controls; they are also useful for controlled backfills.

For a 450 TB estate, do not make one live `ListObjectsV2` walk the primary
bootstrap mechanism.  Configure S3 Inventory (Parquet is preferable), read
the inventory manifest in parallel, and treat it as the immutable baseline.
In parallel, send new object-create events to SQS/EventBridge and ingest those
deltas idempotently.  Reconcile inventory snapshots and event offsets before
declaring a snapshot complete.  This removes day-scale control-plane listing
from the normal path while retaining a recovery path.

For a bucket that cannot use Inventory, partition an initial crawl into
explicit, disjoint prefixes (for example, date prefixes or a pre-existing
hash-prefix layout).  Give every shard its own checkpoint key and run one
enumerator per shard.  Do not start concurrent continuation-token walks of the
same prefix: S3 continuation tokens are sequential and that design can
duplicate or miss keys.

Run workers, Kafka, and RDS in the same AWS region/VPC as the
source. Create a multi-partition Kafka topic and scale worker replicas to
partitions; one worker process is deliberately sequential, while multiple
same-group worker replicas process separate partitions safely. Measure and
raise replica count only after ensuring
RDS connection pools and Kafka partitions can sustain it.

The current database checksum uniqueness gives idempotent content
deduplication, and a PostgreSQL advisory lock serialises competing workers
only when they finish the same checksum. At large scale, retain source version
information (S3 version
ID where versioning is enabled, otherwise ETag/size/last-modified) in the
manifest/event records so that legitimate source updates are not confused with
retries.
