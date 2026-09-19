# Local integrated runtime

This is the isolated review environment for `Feature/Integration`. Do not use the old root Compose files or standalone module frontend servers for this branch. The redesigned `frontend/dist` is the only application served by the gateway.

## Build and start

Use Docker Compose v2, Node 20+, Python 3.11 in containers, and substantial free disk space. AI dependencies and model weights are large; the acceptance machine had 7.6 GiB allocated to Docker, which is not a sizing recommendation for all models concurrently.

1. Create an **untracked** `.integration/stack.env` with strong, independent values for `POSTGRES_PASSWORD`, `INTERNAL_JWT_SECRET`, `NEXUS_JWT_SECRET`, `WATERMARK_SECRET_KEY`, `VAULT_TOKEN`, and `BOOTSTRAP_ADMIN_PASSWORD`. Signing/watermark keys must have at least 32 characters. Set `BOOTSTRAP_ADMIN_EMAIL` (default `admin@platform.internal`). Never commit the file or print resolved Compose configuration with secrets.
2. In `frontend`, run `npm ci`, `npm test`, and `npm run build`.
3. From the repository root, build the common image first, then the model images:

```powershell
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml build gateway
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml build search ai
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml up -d postgres redis kafka qdrant vault-persistent vault-init
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml run --rm migrate
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml up -d --no-build
```

Open `http://localhost:18000`. Only the gateway and PostgreSQL (localhost:15432) have host ports. The Compose project is `smsprsm-integration`; it owns a separate network and named volumes. Do not use `down -v`, prune commands, or `--remove-orphans` on a machine with state you need to retain. Previously running unrelated containers are outside this project.

Local Vault uses file storage in `vault-data`. `vault-init` initializes/unseals it using keys held in the separate `vault-bootstrap` volume and installs the configured local token. **Both volumes are sensitive persistent state.** This is a local development bootstrap, not a production unsealing or key-management design. Connector secrets stay in Vault; PostgreSQL contains only references. The earlier acceptance dev-Vault container was deliberately left intact when introducing the fresh persistent instance; it is not part of the final Compose configuration. No old Vault secrets were exported.

## Configuration and identities

The Compose environment maps a single PostgreSQL instance to separate schemas: `ingestion`, `enrichment`, `search`, `download`, `audit`, `identity`. APIs are separate processes to avoid collisions among their `app`, `core`, and `database` Python packages. `DATABASE_URL` uses asyncpg; `DATABASE_URL_SYNC` uses psycopg2. `DATABASE_SCHEMA` chooses each module's search path. AI's `SOURCE_DOCUMENT_SCHEMA` is `ingestion`.

Browser sessions use `NEXUS_JWT_SECRET` and persisted revocable token hashes. Public registration creates standard users only. The explicit bootstrap administrator can create other administrators at `/auth/users`. No demo login is enabled. The gateway strips browser identity headers and issues 120-second, audience-specific assertions signed with `INTERNAL_JWT_SECRET`. Workers use scoped assertions. Module ports must remain private. Rotating either signing key invalidates the corresponding tokens; watermark-key rotation requires retaining the previous key separately for historical verification if that behavior is needed.

`REDIS_URL` supplies locks, notifications, and Celery. AI additionally accepts `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, and `EVENT_REDIS_URL`. Kafka's ingestion/AI topic is `ai-processing-events`, group `ai-tag-generation`, DLQ `ai-processing-events-dlq`. In the local stack Kafka is private plaintext; enterprise broker authentication is outside this phase. `QDRANT_URL` and `QDRANT_COLLECTION_NAME=multimodal_files` are shared by AI, indexing, and search. Collection creation is explicit and rejects dimensions/distance mismatches (512, cosine). Point IDs are canonical document UUIDs.

## Migration and existing data

`scripts/migrate_integration.py` is the sole integrated setup entry point. It creates schemas, adopts unambiguous known public tables, applies ingestion revisions 001–014 (013 archival, 014 transactional delivery), applies AI's original history through `004_index_delivery` using its dedicated ledger, and applies Search/Download/Audit/identity integration DDL and separate ledgers. Existing revision IDs are retained. Ingestion 005/006 no longer delete tables owned by Download or authentication. Missing schema or database dependencies fail visibly; services do not silently switch to memory or modify schemas at import.

Always test upgrades on a disposable copy first. Ambiguous public/schema table ownership stops migration. Legacy timestamps without zones are interpreted as UTC. Existing public `users`/`refresh_tokens` are preserved, not guessed into a different identity model. For the redesigned frontend's existing JSON/SQLite identity store, after migration and **before first gateway bootstrap**, explicitly mount a read-only copy and run:

```text
python scripts/import_legacy_identity.py --users /legacy/users.json --tokens /legacy/auth.db
```

The importer validates identities, preserves hashes/session revocations, is repeatable, and aborts on conflicts. It does not modify source files. Preserve the old `NEXUS_JWT_SECRET` if unexpired sessions must remain valid. No real developer identity/credential files were imported during acceptance. There is no automatic import of arbitrary legacy account schemas.

## Source and model setup

Create/test connectors as an administrator, then trigger manual scans. Scheduling and browser uploads are not supported. Supply the vendor metadata sidecar required by the ingestion handoff. S3 supports static keys for local testing or the existing AssumeRole configuration. NAS/NFS paths must already be mounted read-only into **both ingestion API and ingestion-worker** at the same container path. NFS mounting is an operator responsibility; an arbitrary `server:/path` string does not mount a remote filesystem. SMB requires reachable shares and credentials. AI and Download never receive vendor credentials; they stream through authenticated ingestion endpoints. Original content remains at its source.

Archive a connector to prohibit future scans and configuration changes while keeping credentials, runs, source references, and historical reads. Hard deletion is allowed only for unused connectors. Active scans must finish before archival.

Search and AI share `open_clip_torch==2.29.0`, OpenAI ViT-B-32 weights, QuickGELU, tokenizer, L2 normalization, and 512-dimensional vectors via `modules/shared/embeddings.py`. Do not change this model for one service alone. Re-enrich/reindex all vectors if the embedding model changes; an old hash-vector collection is not semantically compatible merely because its dimensions match.

AI's `models` volume holds `HF_HOME=/models/huggingface` and `TORCH_HOME=/models/torch`. Supply the RAM++ checkpoint at `/models/ram_plus_swin_large_14m.pth`; the implementation is pinned to the revision in the AI requirements. The full pipeline can also load YOLOv8s, BLIP base, Whisper large-v3, PaddleOCR, BART MNLI/CNN, KeyBERT/SentenceTransformers, spaCy, Presidio, NudeNet, RetinaFace, and Detoxify. Their initial downloads require network access and storage; some require additional resources. Check actual availability before accepting work. The RAM checkpoint is not bundled. Model names/provenance are recorded by the AI module; this phase does not certify model quality.

The base image includes ffmpeg/ffprobe and libmagic. Download metadata watermarking is enabled by default. Optional signal/native codecs retain disabled-by-default settings in `services/download/config.py`; `requirements-codec.txt` installs Python adapters, but patched native codec builds remain separate prerequisites. Do not enable them solely because the Python tests import successfully.

## Processing, visibility, and limits

Ingestion persists document metadata and its AI event in one transaction. `ingestion-outbox` publishes committed work and retries broker failures. The AI consumer verifies streamed size/checksum and cleans temporary files. Kafka offsets are committed after durable terminal outcomes; malformed messages go to the DLQ. Celery serves explicit administration/retry requests. Final AI state adds a durable indexing record; Redis is supplementary. The indexer replays safely across PostgreSQL and Qdrant (the stores do not share a distributed transaction).

Completed and safety-cleared partial records are published. Pending, failed, and `needs_review` records remain administrator operational records. Current license status/expiry is checked in relational queries, details, facets, similarity, streams, and download processing/delivery. Connector identity supplies dataset identity; additional physical locations do not create duplicate catalog results. Vendor metadata remains separate from generated metadata.

Downloads persist owner, batch state, per-file progress/failures, and forensic records. Limits default to 100 IDs, 128 MiB per file, 2 GiB per batch, with bounded temporary packaging and safe UUID-prefixed filenames. Failed packages are never delivered as successful partial archives. Archives expire after 24 hours. Protected browser previews cap at 32 MiB and show an explicit unavailable state for unsupported types. Download byte delivery is logged as started; it does not claim that a client saved every byte.

Search preserves backend order. Hybrid retrieval uses a bounded 10,000-candidate window; vector filtering rejects over 100,000 eligible IDs. These are deliberate local safeguards, not scale certification. Administrative lists are bounded; pagination is implemented where the screen exposes it. No sample catalog is seeded in the integrated runtime.

## Readiness, recovery, and acceptance

`GET /health` is process liveness; `/ready` checks dependencies. Gateway `/ready` aggregates module readiness. AI readiness also reports the required RAM checkpoint. An HTTP 503 is an unavailable dependency, not a fabricated healthy response.

```powershell
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml ps
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml logs --tail 100 ingestion-outbox ai-consumer ai-worker indexer download-worker
docker compose --env-file .integration/stack.env -f deploy/integration/compose.yml restart ingestion-outbox indexer download-worker
```

Restarting workers preserves durable jobs. Review `integration_outbox` attempts/error/delivered_at in the relevant schema. Correct the dependency before restarting or manually retrying failed AI tasks through `/ai/retry/{document_id}`. Do not advance Kafka offsets to hide failed work. AI locks expire after their configured lease; a lost worker may delay redelivery until expiry. Review DLQ messages and task errors before replay. Automatic enumeration of an interrupted manual scan is not implemented; retrigger it after inspecting the persisted run, relying on unchanged-file detection.

Acceptance helpers are under `tests/integration`. They are **test-only** and mutate synthetic data in the isolated project; `projection_workflow.py` deliberately supplies deterministic AI outputs and must never run against production. `acceptance.yml` adds the bounded S3 emulator and fixture mounts. Generate `.integration/nas` fixtures with `create_fixtures.py` mounted as `/fixtures`. Full real-model tests are distinct from these deterministic integration checks. See `INTEGRATION_REPORT.md` for the exact verified results and remaining gaps.

## Restored frontend and visual review

The active UI uses the original `Feature/Re-designed-frontend` design at `92ff6d1`, with service adapters on `Feature/Integration`. The local restoration is not pushed. Build it from `frontend` with `npm run build`. In the current acceptance stack the gateway mounts the repository and serves `frontend/dist`, so refresh `http://localhost:18000` after the build. For an image-only installation, rebuild/recreate the gateway using the Compose build instructions above; do not remove volumes. Existing login credentials and sessions remain valid.

Original layouts remain for every module and both search roles. Missing backend metrics show unavailable; scheduling, separate checksum revalidation, benchmark and unsupported filters remain disabled. Source scans are manual. Create a connector, test it from Sources, then trigger a manual crawl from its details. Archived connectors cannot start scans. Search defaults to hybrid and retains server ordering. Open a file for protected preview/similarity, select files for a persistent batch, and save the archive when ready or from Downloads. AI failures and missing models appear in the administrator inspector; retry queues real work and does not imply successful enrichment.

The isolated reference copy is `.integration/redesign-reference/frontend`, extracted from `92ff6d1` without switching branches. It currently runs on `http://localhost:18001`, with only its local authentication proxy pointed at port 18000. Its prototype fixtures are for visual review only. The integrated application's runtime has no fixture substitution.

To reproduce comparison captures, prepare the ignored reference directory, install its frontend dependencies (or reuse the local frontend dependency directory), run its Vite preview on port 18001, and keep the integrated stack on port 18000. The scripts require Playwright and Edge available to Node. Run from the repository root:

```powershell
node tests/integration/restored-browser.cjs
node tests/integration/restored-ui-regressions.cjs
node tests/integration/redesign-comparison.cjs
node tests/integration/build-comparison-gallery.cjs
```

`restored-browser.cjs` uses the ignored bootstrap credentials, the existing synthetic acceptance catalog, and a one-file-limit empty NAS test directory to verify real operations. The other two browser suites inject test-only responses in their own browser contexts, including 61-result pagination and matched original sample records. They never configure fixtures in the running application. Screenshots and results are stored in `.integration/redesign-qa`; the gallery is `.integration/redesign-qa/comparison/index.html`. Its current optional localhost-only helper serves that directory on port 18002. Stop the reference and gallery helpers when review is complete; leave the integration stack and its volumes intact.
