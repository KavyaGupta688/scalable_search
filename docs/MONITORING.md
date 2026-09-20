# Monitoring and AI findings — 21 September 2026

The RDS-backed application now runs Prometheus and Grafana. No database migrations, local PostgreSQL, changes to shared `samsungdb`, or source-file modifications were required. These changes are isolated to `Feature/Integration`; `main` remains unchanged.

## Access and startup

- Application: http://localhost:18000
- Grafana: http://localhost:13000/d/smsprsm-platform
- Prometheus targets: http://localhost:19090/targets

Grafana uses a separate administrator account. Its username and generated password are in ignored `.integration/monitoring.env` on this PC. Application login is not Grafana SSO. Keep that file private. Anonymous access and sign-up are disabled. Prometheus has no login and is bound only to localhost; do not publish its port externally.

On another machine, copy `deploy/integration/monitoring/.env.example` to `.integration/monitoring.env` and set a unique password. Follow the runtime guide for the existing RDS secrets, images and external model volume. From the repository root:

```powershell
$monitorArgs = @(
  '--env-file', '.integration/stack.env',
  '--env-file', '.integration/rds-runtime.env',
  '--env-file', '.integration/monitoring.env',
  '-f', 'deploy/integration/compose.yml',
  '-f', 'deploy/integration/rds.yml',
  '-f', 'deploy/integration/development.yml',
  '-f', 'deploy/integration/low-memory.yml',
  '-f', 'deploy/integration/monitoring.yml'
)
docker compose @monitorArgs pull prometheus grafana
docker compose @monitorArgs up -d --no-deps --no-build gateway ingestion-worker monitoring prometheus grafana
docker compose @monitorArgs ps
```

Use this complete argument list for subsequent full-stack restarts. Rebuild `frontend/dist` after UI edits. No migration rerun is needed. Grafana environment credentials initialize a new volume; editing the file alone does not change an existing account's password.

Prometheus v3.14.0 and Grafana 13.2.2 are pinned and use separate persistent volumes in `smsprsm-rds`. Retention is seven days or 1 GB, whichever is reached first. Each has a 512 MB memory limit; the internal aggregate exporter has 256 MB. Do not delete volumes to restart services.

## Coverage and boundaries

Six targets are scraped every 15 seconds: Prometheus, aggregate exporter, gateway, ingestion API, ingestion worker and Qdrant. The exporter refreshes every 30 seconds, reading canonical document counts, AI outcomes, download outcomes, four module outboxes, four API readiness checks, latest-attempt AI stage durations, and saved model initialization evidence.

Grafana also plots gateway p95 response-header latency and 5xx rates. These timings exclude completion of streamed downloads. Browser disconnects before forwarding finishes return internal status 499 instead of being miscounted as backend 500 failures. Labels contain bounded route templates/states, not document IDs, content, query strings or user identities. Exporter and gateway metric ports are internal-only. Browser summary and vector-inspection endpoints require an administrator session.

Four Prometheus rules cover unreachable targets, failed/stale collection, unavailable APIs, and delivery backlogs lasting ten minutes. **Alertmanager and email/chat/pager notifications are not configured.** Dedicated host/GPU, RDS, Redis and Kafka exporters and independent AI-worker heartbeats are outside this coverage.

Configuration references: [Prometheus](https://prometheus.io/docs/prometheus/latest/configuration/configuration/) and [Grafana provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/).

## What “unavailable” meant

| UI item | Cause and correction |
|---|---|
| Modality totals/recent discoveries | Summary fields were absent and the frontend displayed literal placeholders. It now reads grouped canonical ingestion counts and the latest three published, currently entitled catalog entries. |
| Storage volume | Now sums canonical ingested byte sizes. This is not the vendor bucket's total storage. |
| AI timing cards | Prototype per-model metrics had no backend contract. Cards now display recorded stage durations/counts, including loading time; they are not per-model benchmarks. |
| Vector/index display | The metadata API did not expose Qdrant state. An administrator endpoint now retrieves the canonical point, checks 512-dimensional compatibility and displays actual values, norm and 32 grouped magnitudes. |
| Document preview | Unsupported browser formats did not display existing extracted text. Text is now shown when present. Unsupported formats, codec failures and oversized media retain explicit explanations. |
| Search timing | Search returned elapsed time but omitted it from durable Audit events. New events now carry timing. Means/p95 use measured searches over the last 24 hours; historical missing timing is not fabricated. |

Downloads' large gap came from a broad CSS rule applying a 340-pixel flex basis vertically. The selector and responsive request layout are corrected.

## AI findings

Inspection found **43 documents: 19 completed and 24 partial**, all published under the current safety/entitlement policy. Recorded stages had no failures. Partial outputs had aggregate confidence roughly 0.57–0.66, below the 0.7 completion threshold; they were not failed model downloads.

The saved manifest reports successful initialization for all 15 components: RAM++, CLIP, YOLO, BLIP, Whisper, PaddleOCR, Presidio, NudeNet, BART MNLI, spaCy, KeyBERT, summarizer, face detector, toxicity and AI-generated-image detector. The UI exposes the check timestamp. This is not evidence of simultaneous model loading or prediction accuracy. The CPU profile loads/releases models on demand.

The benchmark TXT files themselves contain generated asset labels and run identifiers. Old descriptions were dominated by vendor metadata because it preceded extracted text. Version **1.1.1** prioritizes actual content, excludes arbitrary metadata/identifiers from vendor fallback, and avoids mislabelling vendor context as extracted OCR/speech in vision captions. Text-only vendor fallback is explicitly labelled; vendor metadata remains separately stored.

**Existing 1.1.0 records remain preserved** and their old descriptions/tags remain visible until reprocessed. Completed-task reruns are not currently exposed by the retry API; partial/review/failed tasks remain eligible. No bulk re-enrichment or silent relabelling occurred. A fresh read-only test with installed text-tagging models confirmed content-first descriptions and exclusion of supplied benchmark metadata. Short text intentionally bypasses the summarizer.

Processing works, but **model accuracy is not certified**. Representative real files and labelled expectations are needed to assess captions, tags, OCR, transcription, confidence calibration and false-positive PII/safety annotations. Previously documented preview/download limits and deferred NAS integration remain.

## Verification

- Frontend production build and 15 tests passed. No configured frontend type-check suite exists. Vite retains its existing static/dynamic-import warning.
- Gateway/observability: 39 tests passed, including permissions, failed/stale data handling, vector compatibility, cancellation and metric label privacy. Focused Python correctness lint also passed.
- AI correctness/recovery: 25 tests plus eight subtests passed, including content priority and vendor fallback. Adapter tests are separate from actual inference.
- Search: three audit-timing/facet/database-recovery tests passed.
- A fresh actual-model text-tagging smoke passed without rewriting historical outputs.
- Live API checks passed for grouped counts, recent discoveries, normalized 512-vectors, all 15 initialization records, four ready APIs, drained outboxes and Search timing reaching Audit.
- Prometheus configuration and four alert rules passed `promtool check config`; all six scrape targets were up. Grafana datasource health passed.
- Seven live browser groups passed: Overview, Downloads desktop spacing, Downloads mobile, real model/vector/text data, Enrichment mobile, session logout/runtime errors, and authenticated Grafana rendering with the live document count. Screenshots are in ignored `.integration/monitoring-browser/`.

The earlier 5 GB dataset acceptance was not repeated in full for this update. See `docs/DATASET_ACCEPTANCE_20260921.md` for prior end-to-end evidence. Pytest deprecation/read-only-cache warnings did not cause failures.
