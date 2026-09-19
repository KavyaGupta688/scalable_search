# Integration report — Feature/Integration

Date: 20 September 2026 (Asia/Kolkata). The integration code at `2d4ac57` was published to `origin/Feature/Integration` after the user explicitly authorized the push. This is a review candidate. No pull request, main-branch update, history rewrite, production deployment, or enterprise identity rollout was performed.

## Result and confidence

The redesigned frontend is connected to the active Ingestion, AI, Search, Download, and Audit services through an authenticated gateway. Database migrations, durable delivery, indexing, protected source access, persistent downloads, and operational UI connections are implemented.

**This is a reviewable integration candidate, not a claim of full model-pipeline stability.** The isolated local infrastructure and deterministic five-modality integration workflows passed. The actual shared CLIP model passed parity checks. A successful full RAM++/OCR/captioning/speech/safety pipeline could not be established because the required RAM++ checkpoint is absent. AI readiness correctly returns 503 for that condition; the gateway reports ingestion/search/download ready and AI not ready. Further model downloads/resources and real vendor/NAS access need validation before merge acceptance.

## Sources and branch history

Before implementation, the working tree was rechecked, branch history and cached remote commits were inspected, and all three supplied DOCX handoffs were read. Their contents were treated as integration reference requirements. Implementation remained local until the user separately authorized publishing the integration branch.

| Source | Revision | Role |
|---|---|---|
| verified remote main | `871151f0a665e48365a43dd124ce86f60133a96e` | Starting point; Search, Audit, shared backend |
| Ingestion | `e1c9f465f79138f98b5200feccdf5afa91eb1584` | Zero-copy ingestion, entitlements, source access, runs |
| ai_generation | `d4cb583d3055433946bd15001d3d9570b1e4b05c` | AI pipeline, Kafka/Celery, versioned metadata |
| download | `6cbf16b8e0eb54981d1939dd248432761037ddc6` | Packaging, forensic watermarking, optional codecs |
| Feature/Re-designed-frontend | `92ff6d1b735a33a552aed19a898e07e0596f4e03` | Sole application frontend; credential authentication |

`Feature/Integration` starts from the verified remote main object. The separate local `main` reference remains at its original clone revision `11815cc4e220b25f7f220d8dcef49ecaf012548f`; it was not advanced to the newer remote object.

Source ancestry is preserved by local merges: `1176e51` (Ingestion subtree), `e550cb8` (AI), `4e174cb` (Download subtree), `b57e476` (redesigned frontend). Integration fixes follow those merges on the same branch. Local ignored `data/` and credentials were not overwritten. Test secrets, fixtures, logs, and development overrides are ignored under `.integration/`.

## Significant resolutions

- Standalone Ingestion and Download repositories were integrated under their service directories. Their standalone application frontends were excluded. The old Search/Download frontend files were removed, and `frontend/` follows the redesigned application. Prototype frontend fixtures are test-only; runtime fallback metrics, results, connector outcomes, and fake downloads are removed.
- The redesigned merge's incompatible gateway/shared-auth changes were reconciled explicitly. Credential verification and revocable sessions are preserved, with PostgreSQL identity persistence and an explicit non-destructive legacy JSON/SQLite importer. Anonymous administrator and development-login shortcuts are absent from integrated routes. Public registration cannot create administrators.
- Services remain separate processes behind gateway routes. Search's POST root and discovery prefixes are forwarded correctly. Browser-supplied identity headers cannot establish identity; short-lived signed assertions have service audiences and permissions. Standard users cannot administer connectors, ingestion, AI, users, or Audit.
- Ingestion 005/006 no longer drop foreign forensic, download, or identity tables. Original migration identities remain. Ingestion adds 013 archival and 014 outbox; AI adds 004 durable delivery, retaining its separate ledger. Explicit setup owns schema changes; runtime imports do not migrate databases or silently fall back to in-memory stores.
- Ingestion commits document state and AI delivery together. Independent retrying outbox workers survive broker failures. AI terminal-state indexing is durable; Redis notifications are supplementary. Canonical document UUIDs connect Search, Qdrant, source streams, Download, and provenance. Connector identity is dataset identity; vendor and AI metadata remain separate.
- Search uses current entitlement and publication checks across queries, facets, details, similarity, datasets, previews, and downloads. Completed/safety-cleared partial records publish; review/pending/failed records remain operational/admin-only. Query and AI text embeddings use one pinned CLIP configuration, tokenizer, activation, normalization, and deterministic point identity.
- Downloads use persistent owner-bound jobs, per-file state, source size/checksum verification, safe unique archive names, bounded staging, cleanup, and entitlement rechecks during processing and delivery. Failed batches are not exposed as successful archives. Metadata watermarking and persistent forensic verification are retained; optional native codecs remain disabled by default. Download counters commit with job completion so worker retries do not count twice.
- Real authentication, connector/ingestion operations, AI transitions, search, previews, similarity, downloads, denials, and forensic verification reach main's persistent Audit store. Worker delivery keys prevent replayed audit events; run/job correlation survives background work. Filtering, CSV export, and SQL analytics are connected to the UI.
- Visual checks found and fixed autocomplete overlay/focus behavior. Filters retain their selected values even when a similarity response has no facet options. Preview failures and service outages stay visible rather than producing fake success. The redesigned navigation, styling, motion primitives, and responsive shell remain active.

## Validation results

All tests below use the isolated `smsprsm-integration` project, not existing unrelated containers. PostgreSQL, Kafka, Redis, Vault, Qdrant, module APIs, workers, and gateway were started locally. A bounded Moto S3 emulator and a read-only local mounted NAS fixture directory supplied synthetic source bytes. The NAS test exercises the mounted NFS-path adapter; it is **not** proof against a remote NFS server or SMB share.

| Check | Result |
|---|---|
| Frontend `npm test` | 6 contract tests passed; replaced prototype assumptions with real HTTP contracts |
| Frontend `npm run build` | Passed; harmless mixed static/dynamic import chunking warning |
| Gateway/Audit `pytest tests/test_integration_api.py tests/test_audit_extended.py` | 16 passed |
| Ingestion `pytest services/ingestion/tests` | 40 passed |
| AI `pytest modules/ai_tag_description_generation/tests` in actual AI image | 16 passed |
| Search `python -m pytest app/tests` from its backend directory | 11 passed with actual PostgreSQL/Qdrant and CLIP; tests updated for signed identities and isolated fixtures |
| Download supplied tests with optional Python codec adapters installed | 28 passed, 11 skipped because patched native codec binaries are unavailable |
| Shared contract type check | Passed for identity/assertions, visibility, and transactional delivery (3 files) |
| Python parsing | All 287 tracked/new Python files passed at final syntax check |
| Focused Ruff (`E9,F63,F7,F82`) on changed Python files | Passed |
| Broader Ruff rules on gateway/shared/download/search paths | Not clean: 579 findings in the recorded run, including style/import issues, FastAPI default-argument conventions, and executable-bit findings on Windows mounts. This is not a repository-wide lint pass. |
| Frontend type checker | None configured; no TypeScript/type-check suite is claimed |
| Common, AI, Search Docker image builds | Passed; heavyweight AI dependency installation needed a retry after a network timeout |

The final acceptance runtime used the built images with a read-only source bind for testing the current checkout. Build definitions also copy application source and the frontend bundle for normal use; the setup guide documents a fresh build. Test-only optional codec installs are not required for the default metadata-watermark runtime.

### Real infrastructure and workflow checks

- Fresh explicit migrations and repeat migrations passed. A disposable legacy database upgraded ingestion 004→012→014 and AI→004. Actual legacy forensic/download models and records, an older Audit row, and unrelated identity records survived repeated schema adoption. A separate synthetic redesigned JSON/SQLite identity import preserved users, unexpired session validation, revocation, and source files. This does not replace an upgrade rehearsal against a copy of a real deployment database.
- `http_smoke.py` passed credential login, user/admin permissions, public-admin-registration rejection, forged identity rejection, session revocation, gateway route coverage, five-file NAS ingestion, protected streams, archival, and deletion refusal for a used connector.
- `s3_workflow.py` passed real emulator enumeration/source reads, ingestion, canonical IDs, and an unchanged rescan with exactly one durable AI event per document.
- `projection_workflow.py` passed image, PDF, video, audio, and CSV projection, replay without duplicate rows, completed/partial/review/failed/pending visibility, SQL pagination, facets, Qdrant similarity, a five-file archive plus manifest, metadata watermark forensic verification, and denial of a previously ready archive after entitlement expiry. **The AI outputs in this script are deterministic test adapters, not actual full-model enrichment.** It is scoped to its NAS fixture dataset so other acceptance records do not affect assertions.
- `broker_recovery.py` passed: a rolled-back transaction emitted no durable delivery; a committed record stayed pending while the isolated broker was stopped; restarting the broker delivered that record. No unrelated broker was stopped.
- `security_recovery.py` passed cross-user job access rejection, database session expiry, non-destructive identity import/revocation, and repeated index projection. Actual worker restarts retained persisted jobs and delivery state; this is not exhaustive crash-at-every-stage certification.
- `ai_runtime_recovery.py` passed real Kafka malformed-message DLQ delivery, bounded missing-model retries to failed_terminal, readiness 503, checksum rejection, protected S3 materialization, and temporary-file cleanup. Kafka duplicate terminal deliveries were observed committing without re-enrichment.
- `celery_retry.py` passed authenticated manual retry through the real Celery worker, including persisted bounded missing-model failure.
- Actual AI and Search CLIP outputs for `a blue square` matched after rounding to five decimals: SHA-256 `dc6ff86c18e02c0d0987bd0d7ea3f7f651a8dfc918ed850e4a10b2512b5325b0`; both were normalized 512-dimensional vectors. Real `hybrid`, `text`, and `vector` requests returned successfully through the gateway. This checks embedding compatibility, not retrieval quality on a production corpus.
- Browser acceptance passed both-role login/navigation, actual search/filter/similarity requests, protected preview/download behavior, completed archive retrieval, a simulated HTTP 503 with no fabricated results, and mobile rendering. Screenshots were visually inspected. Backend pagination was tested; browser pagination across more than 20 records and every administration edge case were not exhaustively exercised.
- Persistent Audit rows were verified for tested authentication, connector changes, ingestion success/skip, AI lifecycle/indexing, search, preview, similarity, download request/packaging/ready/failure/delivery-start, access denial, and forensic verification.
- Fresh file-backed Vault initialized, unsealed, and recovered after restart. Connector access worked against it. The old dev-Vault container was preserved. Automatic approval review rejected exporting its secrets; no such export occurred. Only known synthetic credentials were recreated in the fresh test instance.

## Reproduction and remaining acceptance work

Use [deploy/integration/README.md](deploy/integration/README.md) for environment mappings, build/start commands, schemas/migration order, source mounts, model checkpoints, ffmpeg/ffprobe, optional codecs, readiness, and recovery. The current local UI is at `http://localhost:18000`; local bootstrap credentials are in the ignored `.integration/stack.env`. Do not publish that file or raw logs containing temporary test tokens.

The integration scripts under `tests/integration/` are intentionally destructive only to their own synthetic acceptance records and must not be pointed at a production database. Populate fixtures and run the deterministic projection workflow with the AI consumer paused, then resume it for real consumer recovery checks. The browser helper requires Playwright and a locally installed Edge browser. Normal module tests run with `python -m pytest` from the relevant module path and configured test dependencies. Local detailed logs and screenshots are in ignored `.integration/`.

Before calling this fully stable or merging:

1. Supply the RAM++ checkpoint and all required remaining model resources, then run successful actual-model ingestion→enrichment→index→search→download flows across all five modalities. Review safety/needs_review outcomes and cold-start memory/CPU behavior. The missing-model failure path passing is not a substitute.
2. Complete real vendor S3/AssumeRole and remote SMB/NFS validation. A subsequent bounded, authenticated listing of the supplied S3 bucket succeeded; it returned four prefixes and no root objects. This establishes listing access only. Real vendor object reads and the full ingestion flow remain unverified; the completed workflow tests used bounded local acceptance fixtures.
3. Rehearse migrations and the optional identity importer against disposable copies of the actual deployed schemas/data. Legacy jobs are preserved for history; old noncanonical S3-key jobs are not silently reinterpreted as new canonical batches.
4. Build/test patched native codecs before enabling their optional settings. Eleven supplied tests remain skipped for that prerequisite.
5. Finish broad lint cleanup and extend browser coverage for large-result pagination and all administration edge cases. No enterprise IdP, scheduler, distributed scaling, or production deployment certification is included.

Additional practical limits: source enumeration still runs as the ingestion module's manual background task; after interruption, inspect the persisted run and retrigger safely rather than assuming automatic enumeration resume. Search uses bounded candidate windows, protected previews have a 32 MiB browser cap, and downloads have configurable file/batch bounds. These choices are documented instead of being represented as unrestricted capability.

## Team inputs needed for acceptance

Credentials alone do not establish stability. The implementation still needs successful actual-model and external-source acceptance, a representative migration rehearsal, and the remaining code and browser checks.

- **AI team:** provide the RAM++ checkpoint, confirmed model versions and remaining model resources, expected hardware requirements, and representative expected outputs for all five supported modalities. Missing-model recovery is verified; successful full-model enrichment is not.
- **Ingestion and source owners:** identify an approved, bounded S3 prefix containing representative files and the required vendor metadata sidecars. Provide entitlement examples and expected scan results. For remote NAS acceptance, provide the reachable SMB share or NFS mount details and access method. The supplied S3 credentials passed listing only.
- **Database and infrastructure owners:** provide a reachable disposable database copy or sanitized deployment snapshot and its migration history. The supplied RDS endpoint timed out on port 5432 before authentication during a TLS-required connection attempt; confirm the required VPN, tunnel, or network allowlist and whether that database is development, staging, or production. No migration was attempted against it.
- **Download team:** provide an existing watermarked sample, its expected forensic record, and the supported verification procedure for compatibility testing. Supply patched native codec builds only if those optional features will be enabled; the default metadata watermarking path already passed local acceptance.
- **Search and Audit owners:** confirm representative expected search/filter/entitlement outcomes and the event names and analytics expected for representative operations. Existing deterministic search, visibility, and persistent Audit checks passed; a real corpus and deployment schema are still needed for acceptance.
- **Frontend and integration owners:** finish broader lint cleanup and browser checks for larger result sets, pagination, and remaining administration edge cases; verify actual-model results and failure states in both user roles.

The isolated stack already provides PostgreSQL, Kafka, Redis, Vault, and Qdrant; extra teammate credentials for these local services are not required. Share any external credentials through the team's secure channel, keep them untracked, and use scoped test access. Replace the live AWS/database credentials shared in chat; retain any prior watermark key needed to verify historical files before changing watermark configuration.

The shareable companion is `docs/Integration_and_Setup_Guide.docx`, combining this report with `deploy/integration/README.md`. The Markdown files remain the editable technical sources for future updates.
