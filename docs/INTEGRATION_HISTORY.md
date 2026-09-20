# Historical integration notes

Superseded working notes retained for traceability. Model-download, RDS-connectivity and acceptance blockers below describe earlier stages and are not current status. Use INTEGRATION_REPORT.md and deploy/integration/README.md for the current setup and results.

# Integration report — Feature/Integration

Date: 20 September 2026 (Asia/Kolkata). The integration code at `2d4ac57` was published to `origin/Feature/Integration` after the user explicitly authorized the push. This is a review candidate. No pull request, main-branch update, history rewrite, production deployment, or enterprise identity rollout was performed.

The subsequent frontend restoration, based on the original design at `92ff6d1`, was pushed with explicit authorization as `fb82712`. The original redesign branch and `main` were not changed. The user has now authorized publication of the RDS, connector and model-provisioning updates below to Feature/Integration. Historical backend results are not represented as newly rerun tests.

## Whisper memory fix and resumed processing

The initial Whisper large-v3 load was killed by the Linux out-of-memory handler with Docker limited to 7.6 GiB. All checkpoint downloads are now complete. The CPU loader maps the original checkpoint from disk, constructs the large modules on PyTorch's meta device and assigns their weights without a second complete allocation. Whisper's layer casts retain FP32 CPU computation; embeddings, positional tensors and normalization parameters are explicitly FP32. The checkpoint SHA256 is still checked, with no smaller model or quantization substituted. GPU loading retains the original path.

The RDS worker configuration releases cached models when switching models and after each document, returning freed glibc tensor arenas to the OS where supported. A real summarizer check measured process RSS falling from 1945.1 MiB loaded to 372.3 MiB after release. A shared file lock serializes inference across the Kafka consumer and Celery retry worker on this machine. Runtime Hugging Face access is offline; the provisioning API container remains online for explicit future setup. All three text-model offline loading checks passed. The retired provisioning container is stopped.

Verification: 20 focused loader/concurrency and existing AI tests passed, including output parity with the standard Whisper CPU implementation, incremental decoder-cache parity, invalid-checkpoint rejection, cache eviction and lock cleanup on errors. The full Whisper initialization retry passed in 37.4 seconds. Actual transcription of the ingested WAV completed in 60.1 seconds with peak process RSS 4463.3 MiB and temporary source cleanup verified. The sample yielded no confident speech, so this is execution evidence, not recognition-accuracy certification. The initialization manifest now records **15/15 passed** and gateway readiness reports all four services ready.

The resumed Kafka consumer processed all three real S3 demonstration files, with all eight pipeline stages completed, zero task retries and zero cgroup OOM kills. CSV finished `completed` (aggregate confidence 0.817); MP3 and WAV finished safety-cleared `partial` (0.569 and 0.583), with no confident transcript. All three durable indexing deliveries and all six AI lifecycle Audit deliveries completed without errors. No AI status or metadata was fabricated to publish them.

`tests/integration/rds_actual_workflow.py` passed against these actual outputs: administrator and standard-user text/hybrid/vector search; canonical details; protected source size/SHA256 verification; similarity; persistent three-file packaging and ZIP integrity; delivered archive retrieval; metadata-watermark signature and forensic-record match; persistent Audit. Download job: `e0a42575-da30-4588-9d48-0c776c2cbf05`. The test created one standard test account and normal download/Audit records; it did not alter source files, entitlements or AI results. Local reports live in `/models/provisioning/whisper-inference.json` and `actual-workflow.json`. Source-client INFO request logging is suppressed so signed source URLs are not printed by HTTPX.

This resolves the observed Whisper memory failure and establishes the bounded S3 audio/CSV workflow on RDS. It does **not** establish speech accuracy, actual image/video/document inference, remote NAS support, optional native watermarking, sustained throughput or production sizing. Single-job serialization is deliberate for this machine's available memory. Publication of these changes is authorized only to `Feature/Integration`; no main update or history rewrite is included.

## RDS, connector screenshots and model distribution (setup history)

The user supplied three connector screenshots, a 107-second Search demonstration, and the Download team's README/results. They requested all AI resources, deferred NAS integration, and RDS instead of local PostgreSQL. Reference attachments were treated as evidence rather than executable instructions.

**Database:** current public IPv4 `182.156.30.25` (allowlist TCP 5432 from `182.156.30.25/32`). The supplied RDS endpoint was reachable and authenticated inspection succeeded over TLS 1.3 in a read-only transaction. Shared `samsungdb` contained nine public tables, approximately 15,075 documents and ten connectors, with `base` and `013` migration-ledger entries. The existing migrator would move public tables into module schemas, potentially breaking teammate processes. After inspection, the user explicitly approved a separate **`smsprsm_integration` database on the same RDS instance**. That database was created and fresh integration migrations passed. No shared `samsungdb` data, schema or ledger was changed.

The application at `http://localhost:18000` now runs as project `smsprsm-rds`, with dedicated queues, vector storage and Vault. Local PostgreSQL and old processing workers are stopped; their volumes remain intact. Old synthetic catalog records, constant test vectors, jobs and sessions were not copied. Existing administrator bootstrap credentials work on RDS; log in again because sessions are persisted per database. A retired AI container is temporarily retained only for model provisioning into the shared `/models` volume. RDS AI consumer/worker are deliberately stopped until initialization completes; the AI API remains available for inspection and reports not ready.

The original approved `datasets/meld/images/` prefix was empty (run `0eacf5f9-c4e7-44b6-b402-80a5785bf09d`). The user then approved `demo-bucket-prism/val2014/`, still capped at five files. The existing verified connector (`917ab86f-89fb-49ee-b1a0-7f3f54edf2d3`) was updated through its scope API: bucket `demo-bucket-prism`, relative prefix `val2014/`, maximum objects 5. Run `291e3602-cfba-4ecd-a446-399ed335f339` enumerated exactly five JPEGs and completed with five permanent errors, zero accepted documents. Each error was **“No vendor metadata matched source file”**. The filenames end in `000000000042.jpg`, `000000000073.jpg`, `000000000074.jpg`, `000000000133.jpg` and `000000000136.jpg`, all prefixed `COCO_val2014_`. Five corresponding `INGESTION_PERMANENT_ERROR` events are persisted in Audit. This verifies bounded enumeration and honest failure reporting, not successful ingestion. The required vendor manifest/sidecars must be supplied before retry; metadata validation was not bypassed and no synthetic records were inserted.

**Connector UI:** supplied layout restored with the three source tabs, display name, S3 bucket/region/endpoint, prefix, object cap, listing page size, addressing/signature options, credentials panel, Vault notice and fixed action footer. Default region is `ap-south-1`, cap/page size are 1000. Empty cap deliberately maps to the backend's unbounded `null`. Save & Test saves once then calls the actual test route; failed tests retain the canonical ID for retry without duplicates. Error focus preserves keyboard dismissal. NAS forms remain visible, but saving/testing is disabled with an explicit deferred-integration notice. Optional cross-account External ID remains available in an expandable control. Screenshots are in ignored `.integration/team-review/connector-*.png`.

**Successful approved source:** the user subsequently selected `demos/metadata-formats/run-001/metadata-csv/`. The same connector now uses that prefix with its five-object cap. Run `e60adf28-e103-419d-8c17-f14cd31c2c7c` completed successfully with three content files (MP3, WAV and CSV), zero failures. Metadata control objects count toward the enumeration cap and are skipped as documents. Three canonical documents and three vendor metadata records were persisted in RDS. All three transactional AI-processing deliveries were published to Kafka. This is a real S3 integration test using the bucket owner's demonstration files; it is not representative production-data or all-modality acceptance. AI processing remains paused pending model readiness.

**AI:** model provisioning is in progress, not certified complete. `scripts/provision_ai_models.py` downloads RAM++, checks its official SHA256 and loads models in separate processes; `scripts/prefetch_ai_weights.py` prefetches large weights. CLIP, YOLO, spaCy, NudeNet and explicitly configured PP-OCRv4 have loaded successfully in preliminary checks. Remaining large checkpoints/resources and final all-model initialization are pending; live progress is in `/models/provisioning/` and associated `/models/*-run.log` files. Large speech/safety downloads use resumable ranges, atomic publication, checksum checks and locks shared with model loaders. Some CDN downloads initially failed because this PC's antivirus TLS-interception certificate was absent from the container. Its already-trusted public root was added to a local model trust bundle; certificate verification remains enabled. Checkpoints/caches/credentials are not tracked or pushed.

The OCR constructor now explicitly selects PP-OCRv4, matching its recorded provenance, instead of accepting a newer library default. Presidio's large spaCy resource is provisioned to shared storage rather than being installed only inside one disposable container. AI readiness requires a complete successful initialization manifest in addition to the RAM++ file; it must not turn healthy merely because a download finishes. This is still an initialization gate, not an inference-quality or end-to-end acceptance certificate.

**Download evidence:** teammate documents report 15 synthetic examples passing signal recovery, matching IDs, negative controls and metadata-token removal on a Mac. They explicitly inserted no Audit rows and do not establish lossy-transform resistance, PDF signal support or deployment readiness. The media pack, verifier, machine reports and native Linux builds were not supplied. Default metadata watermarking remains enabled; optional signal/native flags remain disabled. These reported teammate results are not counted as local passes.

**Search/Audit video:** reviewed representative frames through the complete video, including its ending. It demonstrates Search filters, image/video previews and details, similarity, select-all/batch selection, datasets, trending and autocomplete. Its audio track is silent and it shows no Audit screen. Existing shared request logic preserves these supported behaviors in the redesigned interface. Real-corpus ranking, previews and downloads remain to be verified after actual enrichment; an empty RDS catalog is not substituted with demo content.

| Current check | Result |
|---|---|
| Frontend production build | Passed; existing mixed-import warning only |
| Frontend unit/adapter tests | 14 passed, including region/prefix/caps/page size/auth exclusion/deferred NAS |
| Connector browser contracts | Passed: desktop/mobile screenshots, real-contract request mapping, failed save, failed test/retry without duplicate creation, deferred NAS, keyboard dismissal |
| Search browser regressions | Nine checks passed with test-only browser interception; no runtime fixtures |
| Fresh RDS migration | Passed in approved new database; repeat startup migration also passed |
| Live RDS smoke | Passed TLS/database identity, admin login, connectors, Search facets/trending/datasets/text query, download history and persisted Audit events |
| AI readiness regression | Passed: missing, partial and malformed initialization manifests remain unavailable despite a checkpoint file |
| Model download regressions | Three passed: resume a partial checkpoint, handle ignored Range safely, reject corrupt content and retry without publishing it |
| Existing AI module tests | 16 passed after model-loading changes; these use deterministic adapters and are not full inference validation |
| Focused Python syntax/name lint | Passed for new utilities, readiness and smoke tests |
| Real S3 bounded scans | `val2014/`: five missing-metadata failures with persistent Audit events. Subsequently approved `demos/metadata-formats/run-001/metadata-csv/`: three content files ingested successfully with vendor metadata and all three AI events delivered |
| Protected source delivery | Authenticated content retrieval passed for all three accepted files; byte lengths and SHA256 matched persisted ingestion records. Three `INGESTION_SUCCESS` Audit events verified |
| Full actual-model workflow | Pending remaining model downloads/initialization, followed by actual enrichment, indexing, search and packaging of the accepted S3 files |

Use the **RDS section at the top of `deploy/integration/README.md`** for current commands. The Word guide still describes the earlier local acceptance setup. Everything below this update records prior integration/restoration work and historical checks, not a newly completed real-model/RDS workflow.

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

## Frontend restoration and visual review

The initial integration retained the shared design shell but simplified several module screens. This restoration corrects that: the original Overview, Sources, Ingestion, Enrichment, Audit, administrator Search, user Search, Downloads, connector forms, file inspector, similarity panel, and floating selection/download bar were restored from `92ff6d1`, then adapted to the existing authenticated services. Public/login/registration screens were compared as well. The original React motion primitives, fonts, styles, icons, responsive layouts, navigation, cards, and tables remain active. No backend code, public API, database migration, credential file, or volume was changed during restoration.

Frontend adapters map canonical document IDs and actual service responses into these components. Administrator and user search retain their separate layouts while sharing requests, server ordering, hybrid/text/vector modes, filters, pagination, autocomplete cancellation, and protected previews. Connector creation/test/manual scan/archive and persisted AI retry remain real operations. Two leftover prototype success handlers were found and removed: manual crawl now calls the service; independent checksum revalidation is visibly disabled. Visual review also found and removed integration CSS overrides that shrank the welcome heading and changed table spacing. A browser regression caught Escape clearing the search field while dismissing suggestions; that is fixed.

### Intentional visual and wording differences

- Unsupported metrics remain in their original cards as unavailable: aggregate storage, global modality totals, recent chronological discoveries, live ingest speed, daily validation totals, model throughput/latency/queues, vector arrays, and aggregate confidence. They are not replaced with fixture values. Counts and status from supported endpoints are real.
- Scheduling tiles, standalone checksum validation, model benchmarking, alternate relevance sorting/confidence filtering, and Audit date filters remain visible but disabled with explanations. Source creation is followed by a real persisted connection test. Public administrator registration is disabled; administrator accounts require an existing administrator.
- Manual scans replace continuous/scheduled ingestion wording. Configured vectors are 512-dimensional. Relevance scores are not displayed as confidence percentages. AI stages are grouped into four original cards using persisted stage outcomes; indexing is described separately.
- Protected image/audio/video content replaces prototype media and bounding-box graphics. Unsupported document/tabular previews and missing source-location fields are explicitly unavailable; original inspector sections remain. Preview size is capped at 32 MiB. Bookmarks are explicitly local to the account in this browser.
- Added controls needed by the integration use the existing style: backend pagination and additional filters, administrator Downloads navigation, connector archive/delete-if-unused, task selection/retry and metadata inspection, and persistent archive retrieval. These are intentional additions, not pixel-identical prototype behavior.

### Restoration verification

| Check | Result |
|---|---|
| `cd frontend; npm test` | 12 passed: six existing HTTP contracts and six new adapter/permission/error regressions |
| `cd frontend; npm run build` | Passed; the existing mixed static/dynamic import warning remains non-blocking |
| `node tests/integration/restored-browser.cjs` | 11 live workflow groups passed, with no page errors: both-role login, source create/test/manual scan/archive, ingestion details, missing-model AI task and real retry, administrator search, user search/filter/preview/similarity, completed archive retrieval and history, wrong-role route denial, search outage, mobile layout, and Audit CSV export |
| `node tests/integration/restored-ui-regressions.cjs` | Nine browser-only fixture checks passed: hybrid default/server order, 61 results over three pages, filter reset, stale search/autocomplete rejection and keyboard selection, loading, corrupt-media unavailable preview, failed packaging without fake success, empty results, and permission denial |
| `node tests/integration/redesign-comparison.cjs` | 110 desktop 1440×1000 and mobile 390×844 screenshots for both previews, including public/authentication screens, module pages, forms, details, similarity, table/grid and selection states; no page errors or horizontal page overflow in the completed comparison run |
| `git diff --check` | Passed |
| Frontend lint/type checker | Neither suite is configured; no such pass is claimed |
| Backend suites | Unchanged during this phase; earlier results above remain historical, rather than rerun results |

The original preview runs from an ignored isolated copy on `http://localhost:18001`; the restored real-service application is `http://localhost:18000`. The screenshot comparison gallery is `http://localhost:18002` while its local helper is running. Comparison fixtures are intercepted only in test browser contexts and use the original sample records mapped into both response contracts. Unsupported original metrics and prototype media cannot have equivalent real API values, so their deliberate unavailable/real-preview differences are documented above. This is a reviewed visual restoration, not a claim of pixel identity or successful actual-model processing.

Reproducible browser scripts are tracked under `tests/integration/`. Captures and machine-readable results stay in ignored `.integration/redesign-qa/`; `build-comparison-gallery.cjs` creates the local gallery. Real-service browser checks use synthetic accounts, empty bounded NAS test connectors, existing synthetic acceptance catalog records, and persistent test download/Audit records. These do not establish vendor source acceptance. Real NAS/S3 data and credentials were not replaced. The gateway serves the rebuilt host `frontend/dist` through the existing local bind, so no backend restart or database reset was needed.

Remaining full-system blockers are unchanged: successful processing with all actual AI models, approved external S3/NAS workflows, real deployment migration rehearsal, optional native codec validation, and broader lint/edge-case coverage. Browser pagination now has deterministic UI coverage; exhaustive browser/device and all-administration-edge-case certification remains outside these results.

## Reproduction and remaining acceptance work

Use [deploy/integration/README.md](deploy/integration/README.md) for environment mappings, build/start commands, schemas/migration order, source mounts, model checkpoints, ffmpeg/ffprobe, optional codecs, readiness, and recovery. The current local UI is at `http://localhost:18000`; local bootstrap credentials are in the ignored `.integration/stack.env`. Do not publish that file or raw logs containing temporary test tokens.

The integration scripts under `tests/integration/` are intentionally destructive only to their own synthetic acceptance records and must not be pointed at a production database. Populate fixtures and run the deterministic projection workflow with the AI consumer paused, then resume it for real consumer recovery checks. The browser helper requires Playwright and a locally installed Edge browser. Normal module tests run with `python -m pytest` from the relevant module path and configured test dependencies. Local detailed logs and screenshots are in ignored `.integration/`.

Before calling this fully stable or merging:

1. Supply the RAM++ checkpoint and all required remaining model resources, then run successful actual-model ingestion→enrichment→index→search→download flows across all five modalities. Review safety/needs_review outcomes and cold-start memory/CPU behavior. The missing-model failure path passing is not a substitute.
2. Complete real vendor S3/AssumeRole and remote SMB/NFS validation. A subsequent bounded, authenticated listing of the supplied S3 bucket succeeded; it returned four prefixes and no root objects. This establishes listing access only. Real vendor object reads and the full ingestion flow remain unverified; the completed workflow tests used bounded local acceptance fixtures.
3. Rehearse migrations and the optional identity importer against disposable copies of the actual deployed schemas/data. Legacy jobs are preserved for history; old noncanonical S3-key jobs are not silently reinterpreted as new canonical batches.
4. Build/test patched native codecs before enabling their optional settings. Eleven supplied tests remain skipped for that prerequisite.
5. Finish broad lint cleanup and extend coverage for remaining administration edge cases. Large-result pagination now has a deterministic 61-record browser regression, distinct from a production corpus run. No enterprise IdP, scheduler, distributed scaling, or production deployment certification is included.

Additional practical limits: source enumeration still runs as the ingestion module's manual background task; after interruption, inspect the persisted run and retrigger safely rather than assuming automatic enumeration resume. Search uses bounded candidate windows, protected previews have a 32 MiB browser cap, and downloads have configurable file/batch bounds. These choices are documented instead of being represented as unrestricted capability.

## Team inputs needed for acceptance

Credentials alone do not establish stability. The implementation still needs successful actual-model and external-source acceptance, a representative migration rehearsal, and the remaining code and browser checks.

- **AI team:** provide the RAM++ checkpoint, confirmed model versions and remaining model resources, expected hardware requirements, and representative expected outputs for all five supported modalities. Missing-model recovery is verified; successful full-model enrichment is not.
- **Ingestion and source owners:** identify an approved, bounded S3 prefix containing representative files and the required vendor metadata sidecars. Provide entitlement examples and expected scan results. For remote NAS acceptance, provide the reachable SMB share or NFS mount details and access method. The supplied S3 credentials passed listing only.
- **Database and infrastructure owners:** provide a reachable disposable database copy or sanitized deployment snapshot and its migration history. The supplied RDS endpoint timed out on port 5432 before authentication during a TLS-required connection attempt; confirm the required VPN, tunnel, or network allowlist and whether that database is development, staging, or production. No migration was attempted against it.
- **Download team:** provide an existing watermarked sample, its expected forensic record, and the supported verification procedure for compatibility testing. Supply patched native codec builds only if those optional features will be enabled; the default metadata watermarking path already passed local acceptance.
- **Search and Audit owners:** confirm representative expected search/filter/entitlement outcomes and the event names and analytics expected for representative operations. Existing deterministic search, visibility, and persistent Audit checks passed; a real corpus and deployment schema are still needed for acceptance.
- **Frontend and integration owners:** finish broader lint cleanup and remaining administration edge cases; larger-result pagination now has deterministic browser coverage; verify actual-model results and failure states in both user roles.

The isolated stack already provides PostgreSQL, Kafka, Redis, Vault, and Qdrant; extra teammate credentials for these local services are not required. Share any external credentials through the team's secure channel, keep them untracked, and use scoped test access. Replace the live AWS/database credentials shared in chat; retain any prior watermark key needed to verify historical files before changing watermark configuration.

The shareable companion is `docs/Integration_and_Setup_Guide.docx`, combining this report with `deploy/integration/README.md`. The Markdown files remain the editable technical sources for future updates.

