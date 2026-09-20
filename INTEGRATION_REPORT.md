# Integration report

**21 September dataset acceptance: completed with limitations.** All 41 content objects completed ingestion (37 canonical documents, four duplicates, no failures). Actual AI finished with 16 completed and 21 safety-cleared partial results; all 37 were published. All 12 final API groups passed, including both-role discovery, every document's protected content/details/similarity, a 26-file archive, forensic verification, cross-user ownership, oversized-job rejection, unchanged rescan, session revocation and persistent Audit. Twenty live browser groups and both-role pagination passed. All four services report ready and durable delivery queues are drained. RDS connectivity is restored; shared `samsungdb` remains unchanged.

Local fixes cover large-file polling, AI recovery/safety, bounded memory with process recycling, responsive database calls, explicit outage errors, preview limits and Search's stale database connections. Current regressions: 66 Gateway/Ingestion, 28 AI plus eight subtests, 15 frontend, one Search facet contract and one live stale-connection regression. The final gateway-only recheck passed 26 tests already included in the Gateway/Ingestion count. The final acceptance rerun needed no retry, but earlier Docker/RDS outages and a transient gateway transport failure remain reliability findings. Eleven large MP4s exceed preview/download limits; one AVI cannot play in Edge; CSV/text downloads include a watermark trailer. See [the dataset acceptance report](docs/DATASET_ACCEPTANCE_20260921.md) for evidence and limits. This is a tested development integration, not unconditional stability or deployment certification. The user authorized publishing all changes on `Feature/Integration` on 21 September; `main` remains unchanged. The six-file results below are historical.

Updated 20 September 2026. Branch: **Feature/Integration**. The redesigned frontend and Ingestion, AI, Search, Download and Audit services complete the bounded S3 workflow on RDS with actual model outputs across image, PDF, video, audio and CSV. This is a tested development integration, not production or model-accuracy certification. NAS remains deferred at the user's request.

The latest integrated `ai_generation` commit is incorporated with its ancestry. The preceding published integration was `db50833`; the subsequent AI merge and dataset fixes are included in the user-authorized `Feature/Integration` publication. No pull request, main update or history rewrite is included. Superseded findings are retained in [docs/INTEGRATION_HISTORY.md](docs/INTEGRATION_HISTORY.md).

## Sources and integration decisions

| Source | Revision | Role |
|---|---|---|
| main | 871151f | Search, Audit and shared backend |
| Ingestion | e1c9f46 | Zero-copy sources, metadata, entitlements and runs |
| ai_generation | 5a54af9 | Latest PII review routing, following d4cb583 |
| download | 6cbf16b | Packaging and forensic watermarking |
| Feature/Re-designed-frontend | 92ff6d1 | Sole application frontend |

The working tree was clean at `db50833` before this update. The remote AI branch had one new commit, `5a54af9 Fix PII review routing`, changing its validator, orchestrator and tests. The merge had no textual conflicts. Integration review resolved two behavioral differences:

- PII annotations alone no longer require administrator review. Search previously rejected every PII-labelled record; its publication policy now follows the AI rule while preserving the PII flag for filters and details.
- The upstream change removed the incomplete-safety guard. The integration retains it: incomplete safety analysis remains in review and unavailable for public discovery or downloads. NSFW, excessive toxicity and low confidence retain their review behavior.

The shared toxicity threshold is configured once as `TOXICITY_THRESHOLD`, default 0.8. New enrichments record version **1.1.0**. Existing 1.0.0 outputs retain their historical version; they are not silently relabelled or reprocessed. Administrators can retry eligible partial/review/failed tasks. Completed-task reruns are not offered by the current API.

Earlier resolutions remain intact: separate service processes; signed internal identities behind revocable browser sessions; canonical ingestion UUIDs; transactional Kafka and indexing delivery; shared CLIP vectors; persistent downloads and Audit; connector archival; separate database schemas and migration ledgers. Standalone module frontends and the old main frontend are not served. The original redesigned layouts remain active, including the supplied connector form design.

## Actual workflow verified

The application at `http://localhost:18000` runs in Compose project `smsprsm-rds` against the approved **smsprsm_integration** database. Shared **samsungdb** is unchanged. The project's former local PostgreSQL is stopped with its volume preserved. Kafka, Redis, Qdrant, Vault and package storage are isolated; model storage is shared with the retired provisioning container.

Source: bucket `demo-bucket-prism`, approved prefix `demos/metadata-formats/run-001/metadata-csv/`, connector `917ab86f-89fb-49ee-b1a0-7f3f54edf2d3`. The existing five-object scan accepted MP3, WAV and CSV; metadata objects consume enumeration slots. Three additional scans each selected one exact JPG, PDF or MP4 beneath that prefix. The connector was restored to the parent prefix and five-object cap afterward. Vendor bytes were not modified.

| File | Persisted outcome | Confidence |
|---|---|---|
| sample-mp3.mp3 | Partial, safety cleared | 0.569 |
| sample-wav.wav | Partial, safety cleared | 0.583 |
| sample-csv.csv | Completed | 0.817 |
| sample-jpg.jpg | Completed, version 1.1.0 | 0.863 |
| sample-pdf.pdf | Completed, version 1.1.0 | 0.840 |
| sample-mp4.mp4 | Partial, safety cleared, version 1.1.0 | 0.618 |

All eight pipeline stages finished for each file with zero task retries. Partial results reflect confidence limits, including no confident extracted speech/text on the audio/video samples; no failed stage was hidden. Small demonstration files establish execution and integration, not recognition accuracy on a representative corpus. No AI output or completion flag was fabricated.

`tests/integration/rds_actual_workflow.py` passed against all six actual outputs: both roles' text/hybrid/vector search; dataset filtering; pagination without missing/duplicate IDs; restricted-field exclusion; canonical details; protected source size and SHA256; similarity; persistent packaging; ZIP integrity and retrieval; metadata watermark signature and forensic-record match; persistent Audit. The six-file job was `7e283ad7-06c7-428b-b28c-74f621bd8919`. The test creates a standard account, download and normal Audit activity. Detailed evidence is `/models/provisioning/actual-workflow.json`.

## Validation in this update

| Check | Result |
|---|---|
| AI module and Whisper regressions | 26 passed, including 8 subtests |
| Gateway contracts and Ingestion suite | 54 passed |
| Audit tests in disposable RDS database | 2 passed |
| Search suite with isolated SQL and Qdrant | 11 passed |
| Download with optional Python adapters in a disposable container | 28 passed, 11 native-codec skips |
| Frontend unit and adapter tests | 14 passed |
| Frontend production build | Passed; existing mixed import warning |
| Actual five-modality S3 workflow | Passed, six files and both roles |
| Real-service browser workflow | 11 groups passed, no page errors |
| RDS legacy upgrade and repeated migration | Passed, ingestion 004 through 014 and AI through 004 |
| PII publication and current-access policy | Passed in isolated test resources |

Browser checks cover administrator login, connector design and disabled NAS actions, real ingestion history, loaded image metadata, separate search designs, filters, protected image preview, similarity, completed download/history, wrong-role denial, explicit outage errors, mobile overflow and Audit CSV export. Screenshots/results are in ignored `.integration/rds-browser/`. The outage response is intercepted only in the test browser; other data comes from real services.

The upgrade rehearsal preserved authentication, forensic, download-job and Audit records. It used a generated `legacy_acceptance_*` database on RDS and an independent `integration_validation_*` collection. The PII test placed synthetic metadata/vectors only in those resources and checked idempotent projection, facets, restricted details, unsafe/review exclusions and entitlement enforcement despite stale vector payloads. These fixtures were never inserted into the application catalog.

The Search popularity test previously depended on pre-existing activity. It now records a dataset view and verifies the counter increment. Initial Download test collection lacked optional Python adapters; installing pinned adapters in a disposable container enabled the 28 passes. Eleven native-codec tests remain skipped. No frontend lint or type-check suite is configured, so no such pass is claimed.

Earlier, separately recorded checks cover broker-outage recovery, rollback-safe delivery, malformed Kafka DLQ handling, duplicate deliveries, missing-model retries, checksum rejection/cleanup, session expiry/revocation, download ownership, archival, unchanged rescans and identity import. These were not rerun as stress tests in this update. The earlier 110 visual comparisons and nine deterministic browser checks remain historical evidence. See the historical report for commands and results.

## Setup and operating constraints

All 15 model components pass initialization. RAM++ and the other caches are available locally but intentionally absent from Git. Whisper large-v3 uses its original verified weights with a CPU loader that avoids duplicate allocation. A real WAV run previously peaked at 4463.3 MiB RSS. `AI_MODEL_CACHE_POLICY=single` and a shared lock serialize inference across Kafka and Celery on this 7.6 GiB Docker allocation. Workers use offline Hugging Face caches; provisioning uses the online AI API container.

Use [deploy/integration/README.md](deploy/integration/README.md) for RDS startup, migrations, environment mapping, checkpoints and recovery. Preserve ignored credentials and persistent volumes. Never point the migrator at shared `samsungdb`: it adopts public tables into module schemas. Log in at `/login/admin` with the configured bootstrap account, or register/login a standard account at `/login/user`.

## Remaining acceptance and team inputs

- **AI and Search owners:** representative labelled examples and expected tags, captions, speech, safety and retrieval outcomes. Models execute, but quality, threshold tuning and production-size performance are not certified. Existing partial results remain labelled partial.
- **NAS owner:** remote SMB/NFS access, mounts, credentials and acceptance data remain deferred. Forms stay visible with disabled save/test controls. S3 static-key access is verified; cross-account AssumeRole needs a representative environment if used.
- **Download team:** patched Linux codec binaries and the verification pack only if optional signal/native watermarking will be enabled. These remain off. Default metadata watermarking and persistent packaging passed.
- **Infrastructure owner:** a sanitized deployment schema copy before migration approval. Fresh and constructed legacy upgrades passed on RDS; shared development data was deliberately not migrated. Production backups, TLS hostname verification, key management, sizing and sustained load remain deployment work.
- **Product owners:** representative search relevance, Audit analytics and permission acceptance. Scheduling, browser source uploads, enterprise identity and scale certification remain outside this phase. Unsupported UI telemetry/actions show unavailable or disabled states.

There is no outstanding model download or credential prerequisite for the tested S3 workflow on this PC. A fresh teammate machine still needs secrets, RDS access and model provisioning. The shareable companion is [docs/Integration_and_Setup_Guide.docx](docs/Integration_and_Setup_Guide.docx).
