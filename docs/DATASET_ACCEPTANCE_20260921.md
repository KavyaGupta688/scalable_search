# S3 dataset website acceptance — 21 September 2026

**Status: completed with limitations.** RDS access is restored. All **12 final API acceptance groups** passed against the completed dataset, alongside the live browser checks below. This is a development test with documented limitations, not an unconditional stability or deployment certification. Changes are confined to `Feature/Integration`, based on `e03841d`; the user subsequently authorized their publication on 21 September.

## Source and persisted outcomes

Source: `s3://demo-bucket-prism/demos/csv-multimodal-5gb/20260920-b114b5d3/`.
Connector: `b685120e-f518-43c3-9a93-c1fc01589a6a` (**CSV multimodal 5 GB website acceptance**).
Run: `976f1173-129c-496a-a394-8ce438608e21`.

| Measure | Verified result |
| --- | --- |
| S3 inventory | 45 objects; 4,921,457,459 bytes |
| Content / skipped metadata manifests | 41 / 4 |
| Canonical documents / duplicate source links | 37 / 4 |
| Failed / rejected / skipped content | 0 / 0 / 0 |
| Content bytes processed | 4,921,445,361 |
| AI completed / safety-cleared partial | 16 / 21 |
| AI pending / failed at final processing snapshot | 0 / 0 |
| Published canonical search results | 37 |

Formats include MP3, WAV, CSV, DOCX, PDF, TXT, JPG, PNG, GIF, WebP, AVI, MOV and MP4. Eleven MP4s are roughly 447 MB each. Partial outputs reflect confidence/quality limits; inspected video outputs completed all eight stages with safety analysis complete. No model outputs or completion flags were fabricated. The vendor describes these files as generated benchmark assets: using actual S3 and model inference does not make this a natural-media accuracy evaluation.

The approved RDS database is `smsprsm_integration`. Shared `samsungdb` and vendor source bytes were not changed. Local PostgreSQL remains stopped with its volume preserved.

## Verified website and API behavior

The complete live Edge browser run passed **20 check groups** with no uncaught page errors: public page; administrator login/Overview; source details and S3 form; actual Save & Test, archive, scan prohibition and hard deletion for an unused test connector; ingestion history/details; AI tasks; user administration; both search experiences; standard-user registration; all three search modes; modality filters; image/audio protected previews; explicit unavailable document/tabular/video previews; similarity; image archive delivery; persistent history; role restrictions; empty results; browser-only injected backend outage; mobile layout; Audit export; logout.

A later dedicated browser run passed next/previous search pagination for **both roles**, preserving filters without duplicate results. The earlier 30-result snapshot's second-page limitation was thereby resolved. Screenshots include desktop (1440 x 1000) and mobile (390 x 844) states.

After recovery, the final API runner verified all 37 published results through both roles' text, hybrid and vector search, dataset isolation, pagination, facets and every available modality filter. Every canonical document passed detail, restricted-field exclusion and similarity checks. Small protected sources matched ingestion SHA256/size; large sources passed authenticated header and cancellation checks without unnecessarily downloading another 4.92 GB. Earlier interrupted attempts remain recorded below; the final completed run required no read-only retry.

The final standard-user archive **fc222296-eb9f-40d8-8c47-8bb4df5cb4f8** packaged all 26 eligible files, passed ZIP integrity and supported-format forensic verification, and rejected another user's history/status/content access. Oversized job **ee80f1d2-bac3-4ada-aab9-5852b9d8a12f** failed with a size-limit error, no download URL and HTTP 409 on retrieval. Rescan **f836311d-93ef-4ff0-8a78-dab093a3d685** skipped all 41 unchanged objects, read zero content bytes, had no failures/retries, and preserved the 37 canonical documents. Both sessions were revoked successfully. Search, preview and download-delivery operations were confirmed in persistent Audit.

At final inspection, ingestion, enrichment, Search and Download outboxes all had **zero pending deliveries**. All four service readiness checks passed. The application remains running against RDS.

A separate actual **26-file small-asset archive** passed packaging, retrieval and ZIP integrity. Job: `ddeddbb1-f08d-4ab9-9924-665811a00213`. Forensic signatures and persisted Audit matches passed for **MP3, WAV, JPEG, PNG, AVI and MOV**. This establishes those forensic formats and archive integrity; it does not establish semantic round-trip preservation for every document/tabular format. The download module's existing generic fallback appends a watermark metadata trailer; strict downstream CSV/document consumers still need format-specific validation.

After access returned, all twelve generic-format entries (two each of CSV, TXT, PDF, DOCX, GIF and WebP) also passed original-content-prefix SHA256 checks. Packaged PDF/DOCX structures and GIF/WebP image decoding passed; CSV/TXT retained valid UTF-8. The existing appended watermark trailer means CSV/TXT are not byte-identical originals and CSV row counts are not preserved. Strict consumer compatibility is not inferred from these checks. Evidence: `.integration/dataset-archive-formats.log`.

A real authenticated AVI retry passed all eight AI stages under the new low-memory Celery profile, retained retry count zero, acknowledged the broker task, and recycled its child process. No model weights were changed or substituted.

## Limits observed

- Browser previews are capped at **32 MiB**; downloads at **128 MiB per file**, **2 GiB per batch**. All eleven large MP4s exceed preview/download limits. Live browser tests confirmed clear errors and no downloadable archive on failed jobs. Large files were nevertheless ingested and processed by AI. Limits were not raised silently.
- The tested AVI cannot be decoded in Edge. Its explicit unavailable-preview state, download and forensic checks passed; browser video playback is not claimed.
- Cold login/source-list timeouts occurred during resource pressure. Sustained performance is not certified.
- A resumed run encountered a gateway transport error on one similarity request while services remained ready. Its exact cause was not captured. Sanitized exception-type/correlation diagnostics were added. The final complete rerun had no such error or read-only retry; this does not prove the transient transport issue can never recur.
- This source produced no final review-only records. Animated-image review handling and missing-preprocessing safety are regression-tested; live review-only visibility requires a suitable separate fixture.
- NAS remains deferred. Native codec watermark modes, model accuracy, large-corpus relevance and production hardening are separate acceptance work.

## Problems corrected locally

1. Large source reads exceeded Kafka's five-minute ingestion polling interval. Compose now supplies the existing worker setting with a two-hour default. All large source reads subsequently completed.
2. Busy AI leases no longer consume retries, enter the DLQ or commit past the blocked record. Broker acknowledgement failures cannot overwrite successfully saved output or consume model retries.
3. Python Kafka sessions now tolerate CPU model-loading pauses: 120-second session, 10-second heartbeat, within the actual broker's allowed range.
4. GIFs reach Pillow preprocessing. Animated first-frame-only analysis requires review; missing preprocessing cannot silently pass safety.
5. Gateway authentication, Audit and entitlement database calls run outside the event loop; connection/pool waits are bounded. Database outages now return a sanitized 503 instead of invalid-credential or generic 500 responses. Audit failures are not reported as success; users are told to inspect operation status before retrying.
6. Protected uncompressed streams retain valid Content-Length. Browser previews reject declared oversized content before consuming it and retain streaming limits/cancellation. Compressed upstream lengths are not incorrectly forwarded after decoding.
7. Dataset filters display authorized connector names while retaining canonical IDs and server ordering.
8. An optional `deploy/integration/low-memory.yml` profile caps each AI container at 4 GiB RAM / 5 GiB combined RAM and swap. Kafka recycles after durable output and acknowledgement; Celery uses one prefork child per task. Both retain the shared inference lock, original weights and safety checks.
9. After RDS recovered, Search reused a stale async database connection and returned 500. Its pool now checks connections before checkout and recycles aged connections. A live regression terminated only the test process's own idle RDS backend and verified automatic reconnection without touching application sessions or records. The service was restarted to load the fix.

## Recovery history — connectivity blocker resolved

RDS TLS access succeeded after confirmation for public IP **157.51.137.81**, allowing all processing to finish. Docker/WSL suffered three interruptions with severe host memory pressure (about 400–650 MiB free on this 16 GiB PC); the exact VM crash cause was not proven. Restarts were authorized. The user separately confirmed selecting factory reset. A stale Docker runtime socket then blocked startup; only the verified temporary runtime directory was moved to a backup. The original data disk, containers and named volumes survived and were verified.

Abandoned task leases were cleared only after both processors stopped, with exact document/owner checks and Audit records. One identified unacknowledged retry was restored transactionally. Queues were not purged, offsets were not advanced to hide work, and outputs were not marked complete manually.

A 4 GiB cap alone caused a confirmed AI container OOM/exit 137 at **21:26 UTC on 20 September**. The subsequent recycling profile processed the remaining consecutive large files with clean acknowledged restarts. This is measured recovery on this PC, not a certified hardware minimum.

At **22:05 UTC / 03:35 IST**, final protected-content acceptance failed while writing Audit after RDS connections timed out. At 03:36 IST the PC's public IP was **157.51.128.138**; a direct TCP connection to RDS port 5432 also timed out. Docker remained running. The infrastructure team must confirm RDS availability and allow **157.51.128.138/32 TCP 5432**, or provide a stable approved network. An allowlist mismatch is plausible; it is not proven to be the only cause. Gateway readiness correctly returned 503.

**Follow-up after the user's access update:** Windows can now establish TCP to RDS, but the application containers still cannot. Repeated public-IP checks show Windows using **157.51.128.138** and Docker using **157.51.114.38**. Both resolve RDS to the same IPv4 address; an explicit container IPv4 connection still times out, so this is not just an IPv6 error. The infrastructure team was asked to additionally allow **157.51.114.38/32 on TCP 5432**. Gateway readiness remains 503; the final acceptance run has not been restarted and no new pass is claimed.

**Second access update:** Docker RDS connectivity and all four backend readiness checks recovered. All integration outboxes had zero pending records. The first resumed acceptance exposed the stale Search connection fixed above; the next run passed both-role discovery and filtering and continued into per-document checks. Both-role live browser pagination passed again after recovery. These updates supersede the earlier connectivity blocker, while retaining its history.

The subsequent similarity transport failure was retained as a reliability finding. The acceptance runner permits one explicitly logged retry only for unavailable read-only requests; download creation and ingestion triggers are never automatically repeated. The final completed run used **no retries** and returned `passed_with_limitations`, with eleven files above the configured download limit. The unchanged rescan completed at **22:40:54 UTC on 20 September / 04:10:54 IST on 21 September**. No connectivity prerequisite remains outstanding at delivery.

## Validation and evidence

| Check | Current result |
| --- | --- |
| Gateway contracts and Ingestion tests | 66 passed; two dependency deprecation warnings |
| AI module tests | 28 passed plus 8 subtests |
| Search facet label contract | 1 passed |
| Search stale-connection recovery against RDS | 1 passed |
| Frontend tests | 15 passed |
| Frontend production build | Passed; existing mixed static/dynamic import warning |
| Focused Python correctness lint | Passed |
| Compose configuration and whitespace checks | Passed |
| Live browser | 20 groups plus both-role pagination passed |
| Full final API acceptance | All 12 groups passed; eleven oversized-file delivery limitations |
| Final readiness / durable delivery | All four services ready; all outboxes drained |

No frontend type-check suite is configured. Earlier six-file/module-wide test results remain historical in `INTEGRATION_REPORT.md` and must not be added to these counts.

Ignored local evidence: `.integration/dataset-acceptance-completion.log`, `dataset-acceptance-results.json`, `dataset-final-outboxes.json`, `dataset-browser-complete/results.json`, `dataset-browser-pagination/results.json`, `dataset-browser-recovered.log`, `dataset-delivery-probe.log`, `dataset-archive-formats.log`, `dataset-low-memory-retry.log`, `dataset-gateway-recovery-tests.log`, `dataset-gateway-final.log`, `dataset-ai-regression.log`, `dataset-search-recovery.log`, and `dataset-facet-label-test.log`. Browser directories contain screenshots. The final machine report has status `passed_with_limitations`; earlier failed-run logs are retained separately. The final gateway-only rerun passed 26 tests; these are a subset of the 66 Gateway/Ingestion tests, not additional tests.

## Reproduce the completed acceptance

Use the existing Compose project and add `-f deploy/integration/low-memory.yml` after the RDS/development overrides. Preserve all volumes and credentials. Verify readiness, then run:

```powershell
docker exec smsprsm-rds-ai-1 python -u tests/integration/dataset_acceptance.py b685120e-f518-43c3-9a93-c1fc01589a6a 976f1173-129c-496a-a394-8ce438608e21
```

This checks the existing completed run, creates test accounts/download jobs and one bounded unchanged rescan, and records ordinary Audit activity. It does not repeat completed AI inference. All these final checks have now passed. Remaining limitations concern large-file delivery settings, browser codecs, CSV/text watermark compatibility, sustained reliability, representative model quality, NAS and deployment acceptance—not unfinished work in this bounded test sequence.

For browser reruns with Playwright/Edge available:

```powershell
node tests/integration/dataset-browser.cjs b685120e-f518-43c3-9a93-c1fc01589a6a --complete
node tests/integration/dataset-browser.cjs b685120e-f518-43c3-9a93-c1fc01589a6a --pagination-only
```

Acceptance testing itself did not push changes. The user subsequently authorized committing and pushing the integration work to `Feature/Integration`. No merge into main, source mutation, shared-database migration or data-volume reset was performed by this test work.
