# Integrated runtime setup guide

**21 September monitoring update:** Prometheus and Grafana are running locally with real Overview/AI metrics. See [monitoring setup, credentials location, coverage and validation](../../docs/MONITORING.md). Include its environment file and Compose override when restarting this PC's stack.

## Current environment

The application uses **smsprsm_integration on RDS** over TLS and runs at `http://localhost:18000`. It does not use local PostgreSQL. Shared `samsungdb` is outside the migration scope. Keep `Feature/Integration` checked out; the gateway serves the restored React build from `frontend/dist`. Do not start standalone module frontends or the old root Compose configuration.

Project `smsprsm-rds` owns separate Kafka, Redis, Qdrant, Vault and package volumes/networks. Only `smsprsm-integration_models` is shared with the former provisioning environment. The RDS override disables local PostgreSQL and removes it from migration dependencies. Never use `down -v`, volume pruning or orphan removal when retaining this environment.

## Credentials and prerequisites

Use Docker Compose v2, Node 20 or newer and the Python 3.11 container images. AI dependencies/checkpoints require substantial disk space. The tested Docker memory allocation is 7.6 GiB with serialized inference; it is not a throughput sizing recommendation.

Create ignored `.integration/stack.env` with independent values for `INTERNAL_JWT_SECRET`, `NEXUS_JWT_SECRET`, `WATERMARK_SECRET_KEY`, `VAULT_TOKEN`, `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD`. Signing/watermark keys need at least 32 characters. `POSTGRES_PASSWORD` is required for base Compose interpolation although the local database is disabled. Keep secrets untracked and never print resolved Compose configuration.

Create ignored `.integration/rds-runtime.env` using URL-encoded credentials:

```text
RDS_DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:5432/smsprsm_integration?ssl=require
RDS_DATABASE_URL_SYNC=postgresql+psycopg2://USER:PASSWORD@HOST:5432/smsprsm_integration?sslmode=require
```

The RDS security group must allow the application's current public egress IP on TCP 5432. Check from inside Docker as well as Windows: during 21 September acceptance, Windows used `157.51.128.138` while Docker used `157.51.114.38`. Windows connectivity alone did not establish application access. After the second allowlist update, Docker connected and all four service readiness checks passed. Recheck after changing networks or VPN; these addresses are observations, not permanent settings. These settings require encryption; configure certificate/hostname verification and least-privilege roles for deployment.

S3 credentials are entered in the administrator connector form and stored write-only in Vault. PostgreSQL stores only the Vault path. Optional `MODEL_CA_BUNDLE` selects an approved public trust bundle for corporate/antivirus interception during model downloads. Keep HTTPS verification enabled.

## Build and start

In PowerShell at the repository root, define the RDS configuration once per shell:

```powershell
$composeArgs = @(
  '--env-file', '.integration/stack.env',
  '--env-file', '.integration/rds-runtime.env',
  '-f', 'deploy/integration/compose.yml',
  '-f', 'deploy/integration/rds.yml',
  '-f', 'deploy/integration/development.yml'
)
```

In `frontend`, run `npm ci`, `npm test` and `npm run build`, then return to the repository root. On a fresh machine, create the external model volume, build images and start dependencies:

```powershell
docker volume create smsprsm-integration_models
docker compose @composeArgs build gateway
docker compose @composeArgs build search ai
docker compose @composeArgs up -d redis kafka qdrant vault-persistent vault-init
docker compose @composeArgs run --rm migrate
docker compose @composeArgs up -d --no-build
```

Migrations are already applied on this PC. For an ordinary restart, use only the last command. During initial provisioning, stop the AI workers and restart only after the complete manifest passes:

```powershell
docker compose @composeArgs stop ai-worker ai-consumer
docker compose @composeArgs exec ai python scripts/provision_ai_models.py
docker compose @composeArgs up -d --no-build ai-worker ai-consumer
docker compose @composeArgs ps
```

Do not start a second provisioner while one is active. Initialization must succeed before the worker startup command. This PC already has all 15 components ready and both workers running. Only the gateway is published to localhost in the RDS configuration.

## Login and frontend

Use `/login/admin` for the bootstrap account in the ignored environment file. Standard users register/sign in at `/login/user`. Public registration cannot create administrators; the bootstrap administrator can manage users through `/auth/users`. Old local-database sessions require a fresh login on RDS.

The frontend preserves `Feature/Re-designed-frontend` at `92ff6d1`, including separate administrator/user Search designs. Restoration was pushed as `fb82712`; the later RDS/model fix was pushed as `db50833`. The latest AI update remains local for review. Rebuild `frontend` and refresh after edits. Image-only installations must rebuild/recreate the gateway without removing volumes.

Sources support manual scans. The connector form follows the supplied screenshots. Cap/page size default to 1000; blank cap deliberately means unbounded. Save & Test saves once and performs a real connection test; failed tests retain the saved ID. Archive prevents new scans and edits while retaining historical reads. Hard deletion is allowed only when unused.

All module screens use real endpoints. Missing telemetry is labelled unavailable. Scheduling, browser source upload, separate checksum revalidation, benchmarking and unsupported controls do not imply available backend operations. Protected image/audio/video previews use source bytes; unsupported or oversized previews have explicit unavailable states. NAS forms remain visible with saving/testing disabled until the deferred integration is approved.

## Service and database contracts

Separate API/worker processes avoid Python package collisions. Schemas are `ingestion`, `enrichment`, `search`, `download`, `audit` and `identity`. `DATABASE_URL` uses asyncpg; `DATABASE_URL_SYNC` uses psycopg2. `DATABASE_SCHEMA` sets each search path. AI uses `SOURCE_DOCUMENT_SCHEMA=ingestion`.

Sessions are persisted and revocable. The gateway validates them, strips caller-selected identity headers and issues audience-specific internal assertions lasting 120 seconds. Workers receive scoped identities. Module ports must remain private. Signing-key rotation invalidates tokens; retain historical watermark keys separately when old files must remain verifiable.

Kafka topic `ai-processing-events`, group `ai-tag-generation` and DLQ `ai-processing-events-dlq` handle ingestion deliveries. Redis provides locks, Celery and notifications, not the sole indexing queue. Qdrant collection `multimodal_files` uses 512-dimensional cosine vectors and canonical document UUIDs. AI and Search share pinned OpenAI ViT-B-32 weights, QuickGELU, tokenizer and normalization through `modules/shared/embeddings.py`. Changing that model requires re-enrichment/reindexing; equal dimensions alone do not establish compatibility.

The ingestion worker allows `INGESTION_MAX_POLL_INTERVAL_MS=7200000` (two hours) between Kafka polls while hashing a source object. The five-minute library default was exceeded by a real 447 MB S3 read during the larger dataset test. Set this allowance above the longest expected source read and recreate only `ingestion-worker` after changing it. Offset commits remain after the database commit; interrupted reads can be redelivered without duplicating canonical documents or terminal run counters. This setting does not increase preview or download size limits.

Local Kafka is private plaintext. Vault uses persistent file storage plus a separate bootstrap volume holding initialization/unseal material. Preserve both sensitive volumes. This is development bootstrap, not production key management.

## Migration and legacy data

`scripts/migrate_integration.py` creates schemas, adopts unambiguous module-owned public tables, applies ingestion 001 through 014, AI through 004 with its dedicated ledger, then Search/Download/Audit/identity DDL and ledgers. Ingestion 013 adds archival and 014 adds durable delivery. Revisions 005/006 no longer drop other modules' tables. Ambiguous ownership stops migration. Runtime imports do not modify schemas or silently switch to in-memory dependencies.

Never migrate shared `samsungdb`. Fresh setup and a constructed legacy upgrade passed in separate RDS databases, preserving authentication, forensic, download and Audit records through repeated adoption. Rehearse on a sanitized deployment copy before production approval.

An explicit legacy JSON/SQLite identity importer can run after migration and before gateway bootstrap, using mounted read-only source files:

```text
python scripts/import_legacy_identity.py --users /legacy/users.json --tokens /legacy/auth.db
```

It validates conflicts, preserves hashes/revocations and leaves originals unchanged. Retain the prior JWT signing key if unexpired sessions must survive. Unrecognized public identity schemas are preserved without guessing their mapping.

## Source and AI setup

The approved connector uses bucket `demo-bucket-prism`, relative prefix `demos/metadata-formats/run-001/metadata-csv/`, cap five objects. Do not include the bucket name in the prefix. Vendor manifests or supported sidecars must match the content. Metadata objects consume enumeration slots but are not ingested as documents. The earlier `datasets/meld/images/` was empty; `val2014/` lacked metadata and correctly reported permanent failures. Vendor bytes remain at the source; AI and Download use protected ingestion streams without receiving vendor credentials.

Six real demonstration files are indexed: MP3, WAV, CSV, JPG, PDF and MP4. Three exact-object scans each accepted one JPG/PDF/MP4, then the parent prefix and five-object cap were restored. Remote SMB/NFS remains deferred. Future NFS sources must be mounted read-only at the same path in ingestion API and worker; a typed server path does not mount a filesystem. Cross-account AssumeRole requires its own acceptance environment if used.

Caches live under `/models`, including Hugging Face, Torch, Whisper, YOLO and auxiliary resources. RAM++ is `/models/ram_plus_swin_large_14m.pth`, checked against the official SHA256. Other resources include YOLOv8s, BLIP base, Whisper large-v3, PP-OCRv4, BART MNLI/CNN, KeyBERT/SentenceTransformers, spaCy/Presidio, NudeNet, RetinaFace and Detoxify. Checkpoints are not distributed through Git. `scripts/prefetch_ai_weights.py` can prefetch large weights; downloads use resumable ranges, locks, checksums and atomic publication.

AI readiness requires the complete initialization manifest `/models/provisioning/results.json`, not merely a checkpoint file. Workers set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; the AI API remains online for provisioning. After repairing a component, verify its initialization/inference before atomically replacing that manifest entry, or rerun the complete provisioner with workers stopped.

Whisper uses unchanged large-v3 weights and FP32 CPU computation without quantization. Memory-mapped assignment avoids duplicate model allocations. `AI_MODEL_CACHE_POLICY=single` releases models between stages/documents. `AI_MODEL_EXECUTION_LOCK=/models/inference.lock` serializes Kafka/Celery inference; both processes require the same model volume. Verified WAV inference peaked at 4463.3 MiB RSS. Do not increase concurrency without measurement. `scripts/verify_whisper_runtime.py DOCUMENT_ID` checks actual inference, memory and cleanup without logging transcripts.

## Publication and download behavior

Ingestion commits metadata and the AI outbox record together. Broker failures retry; rolled-back documents produce no delivery. AI verifies source checksum/size and cleans temporary files. Terminal state creates durable indexing work. Replays idempotently update SQL and Qdrant, which do not share a distributed transaction. Celery serves explicit retries; Redis notifications supplement durable records.

New enrichment version 1.1.0 incorporates `ai_generation` commit `5a54af9`: PII is an annotation/filter and does not automatically require review. Completed and safety-cleared partial results are published. NSFW, toxicity at or above `TOXICITY_THRESHOLD` (default 0.8), incomplete safety analysis and review-only tasks remain excluded. Set the threshold in `.integration/stack.env`; Compose supplies it to AI and indexing. Existing outputs retain version 1.0.0. Eligible partial/review/failed tasks can be retried; the API does not rerun completed tasks.

Current entitlement status/expiry is enforced in discovery, facets, details, similarity, source reads and download processing/delivery. Restricted AI fields remain administrator-only. Dataset identity is the canonical connector; vendor and AI metadata remain separate. The runtime seeds no sample catalog or constant vectors.

Downloads persist ownership, per-file results and forensic records. Defaults: 100 IDs, 128 MiB per file, 2 GiB per batch and 24-hour archive lifetime. Temporary storage is bounded, names are safe/unique and failed packages cannot appear as successful incomplete ZIPs. Browser previews cap at 32 MiB. Audit delivery events mean transfer started, not proof that the client saved every byte.

ffmpeg/ffprobe and libmagic are installed in the base image. Metadata watermarking is on by default. Optional signal/native flags in `services/download/config.py` remain off. Python adapters in `requirements-codec.txt` do not supply patched native binaries; eleven native tests remain skipped.

## Validation and recovery

`/health` checks process liveness; gateway `/ready` aggregates dependencies and returns 503 for unavailable resources. Inspect persisted task errors, outbox attempts/errors and DLQ messages before retrying. Never advance Kafka offsets to hide failed work.

```powershell
docker compose @composeArgs ps
docker compose @composeArgs logs --tail 100 ai-consumer indexer download-worker
docker compose @composeArgs restart ingestion-outbox indexer download-worker
```

Restarts preserve jobs/storage. Locks have leases, so lost workers can delay redelivery until expiry. Retry eligible tasks through the administrator UI after fixing dependencies. Interrupted manual source enumeration needs inspection and a manual retrigger; unchanged-file detection avoids duplicate canonical content.

The Python AI consumer uses a 120-second Kafka session timeout and a 10-second heartbeat interval (`KAFKA_SESSION_TIMEOUT_MS` / `KAFKA_HEARTBEAT_INTERVAL_MS`). CPU checkpoint loading exceeded its previous ten-second lease during the large-source run. This trades slower dead-worker detection for tolerance of model-loading pauses; the broker must allow the configured session timeout. A failed offset acknowledgement is retried by redelivery without consuming model retries or replacing already persisted results.

Search checks pooled database connections before reuse and recycles them after 30 minutes. This was verified by terminating only a test process's own idle RDS connection and successfully reconnecting. Connection checks cannot recover a transaction interrupted mid-request; preserve visible errors and retry read operations after readiness recovers.

On this 16 GiB Windows PC, repeated Docker/WSL interruptions occurred with less than 1 GiB free host RAM. A memory cap alone subsequently killed the AI container during consecutive videos (recorded OOM/exit 137). Add `-f deploy/integration/low-memory.yml` after the RDS/development overrides for the optional CPU profile: each AI container gets 4 GiB RAM plus at most 1 GiB swap. Kafka exits normally after one durably saved and acknowledged document (`AI_MAX_DOCUMENTS_PER_PROCESS=1`), and its restart policy creates a fresh process. Celery uses one prefork child with `--max-tasks-per-child=1`; unlike the solo pool, this releases native runtime memory after each retry. Both retain the shared inference lock, original model weights and safety checks. Normal per-document Kafka exits are intentional, not failed enrichments. This profile is not a certified minimum or the default deployment. Keep adequate host headroom, inspect memory/worker failures, and never reset volumes or mark tasks completed to bypass resource problems. The acceptance report records validation and remaining limitations.

For actual-source acceptance on this PC, run `tests/integration/rds_actual_workflow.py` inside the AI container with connector `917ab86f-89fb-49ee-b1a0-7f3f54edf2d3` and `--expected-documents 6`. It creates one standard test user and ordinary download/Audit records without substituting AI output. Run `node tests/integration/rds-browser.cjs` from the host with Playwright and Edge available for both-role browser checks.

Other helpers, including `projection_workflow.py`, `legacy_upgrade.py` and `pii_publication.py`, deliberately create synthetic fixtures and belong only in isolated acceptance resources. The PII helper refuses application database/collection names. The older `restored-browser.cjs` targets a synthetic NAS catalog; use `rds-browser.cjs` against RDS instead. Visual suites inject responses only into their own test browser and do not configure runtime fixtures.

Search has a 10,000-candidate hybrid window and rejects vector filtering above 100,000 eligible IDs. The additional 4.92 GB dataset completed ingestion and actual-model processing for 37 unique documents (16 completed, 21 cleared partial). After RDS recovery, all 12 final API groups passed, including protected content, download ownership, forensic checks, unchanged rescan and Audit; the live browser checks also passed. Final readiness passed and outboxes drained. See `docs/DATASET_ACCEPTANCE_20260921.md` for the earlier outages, transient transport failure and actual validation scope. Eleven large MP4s exceed current preview/download limits. Generic-format archive entries passed preserved-prefix/readability checks, but CSV/text include a watermark trailer and strict downstream compatibility remains unverified. Sustained load, every media encoding, model-quality review, remote NAS, optional native codecs and deployment hardening remain separate acceptance work. Current results are recorded in `INTEGRATION_REPORT.md`.
