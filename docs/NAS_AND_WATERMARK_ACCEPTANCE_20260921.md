# NAS and download watermark integration — 21 September 2026

Work remains local on Feature/Integration. Prior unrelated integration changes were preserved. No push, shared samsungdb migration, or source-file mutation was performed.

## NAS status and host setup

The NAS form is enabled with UNC/subfolder validation and per-connector SMB credentials. SMB uses isolated session caches, bounded connection establishment, read-only source streams, and traversal checks. Blocking connection setup runs outside the async event loop. Credentials remain in Vault and are not returned by the API.

The authorized connector **NAS Tagged Search Test** is saved as `ffc67731-17bb-4d7d-b85c-1cf4a9ebf0ec` for `\\100.72.198.49\IngestionDemo\tagged-search-test-01`, maximum 20 files. The real connection test timed out on TCP 445 from both Windows and Docker. No run was triggered. Tailscale lists only this client (`100.104.100.10`), and reports **no matching peer** for the NAS. Credentials have not yet been authenticated against the host. Changing the subfolder cannot fix missing network reachability.

On the host laptop: connect Tailscale, confirm its IP, share the host through the Tailscale Machines console, and accept the invitation using this client's Tailscale account. Enable incoming connections. Keep the host awake. Ensure `IngestionDemo` is an SMB share and the supplied reader account has both share-level and NTFS read/list permissions. Allow TCP 445 from this client's Tailscale IP in Windows Firewall and any custom Tailscale access policy. Do not expose SMB through a public router rule.

After connectivity is fixed, rerun `tests/integration/nas_acceptance.py` in the gateway container with `NAS_ACCEPTANCE_CREDENTIALS` pointing at the ignored local credentials file. It reuses the connector, tests the connection, and triggers only after a verified response. The initial `nas-smb-10gb` request (250-file cap) has not been tested either; the user subsequently selected the tagged folder as the immediate target.

Acceptance still pending: ingest, enrich, index, preview, download, audit, unchanged rescan, canonical deduplication, and exact-tag results. Expected counts scoped to this connector: dog 1, flower 1, car 1, beach 1, pizza 1, city 1, red 3, water 2, outdoor 5, search_dog_001 1. Compare exact vendor tags separately from AI-added tags and broad semantic queries. Manifest/sidecar metadata remains required for NAS; inspect it when connected.

## Subsequent NAS run and ingestion telemetry verification

The earlier network blocker above is superseded by the user's successful **NAS-First_attempt** run on September 21. Read-only RDS inspection and authenticated browser checks verified connector `0f91a09b-127a-4a9c-b61a-f844f1479f3f`, run `3261f4cf-8733-48a9-8031-4705671cf6c3`, against the tagged NAS folder: 20 processed, 18 newly ingested canonical documents, two checksum duplicates, zero skips/rejections/failures, 23,662,037 bytes. This verifies this run's ingestion, not the still-pending full NAS download/exact-tag acceptance matrix.

The Ingestion Monitor's three top cards and OCR/embedding labels were hard-coded placeholders, not reported NAS errors. They now use administrator-only database telemetry, refreshed every five seconds. Recent speed sums completed-file bytes over 60 seconds; it is not an instantaneous SMB network measurement and falls to zero when idle. Validated Today counts successful and duplicate outcomes since midnight in the browser's timezone, excluding unchanged skips. Duplicates Detected counts duplicate outcomes across all recorded runs, not unique duplicate physical objects. Aggregates are independent of the latest-50 table limit. The real snapshot showed 68 validated today and six duplicate outcomes globally.

The details dialog refreshes run records and items, displays the NAS source folder, labels lifetime throughput as Run average, and shows discovered items still awaiting an outcome instead of an unmeasured worker-process count. OCR, AI status, and persisted Search index/publication counts are joined to the run's distinct canonical document IDs. Reused documents may have older enrichment; persisted index state does not certify current Qdrant health. Errors are displayed, and a failed metrics request does not become fabricated success. Separate checksum revalidation remains disabled because checksums are already validated during ingestion and no separate operation exists.

At 07:17 UTC, the actual pipeline had four partial results, three completed, one in progress and ten awaiting delivery; seven records were indexed/published, with no task error messages. The partial examples inspected had confidence about 0.66–0.68, below the configured 0.70 completed threshold. Ingestion completion does not imply AI completion; CPU workers continued processing without interruption during this change.

Validation: frontend production build and 17 tests passed; 33 backend observability/gateway tests plus two new endpoint authorization cases passed. The live Edge browser verified numeric API values, NAS details, desktop/mobile layouts and no JavaScript errors. Screenshots are retained locally under ignored `.integration/ingestion-metrics*.png`. Only the gateway was restarted; no ingestion/AI worker restart, database migration or new scan was required. Changes remain local on Feature/Integration.

## Download execution and administrator tracing

Previous integrated execution was a dedicated PostgreSQL-polling process, not Celery. Current execution uses a dedicated Redis/Celery `downloads` queue. Small requests (at most two files, total at most 2 MiB, no configured signal transformation) use an API-process background thread when a Redis admission slot is available. This is direct processing, not a bypass of watermarking: both paths create an audited, persistent ZIP and serve it through the protected delivery endpoint. Busy/signal/larger requests use Celery. There is one fast slot and two Celery processes by default; these are development limits, not a throughput guarantee.

PostgreSQL remains the durable source of truth. Initial broker publication occurs after commit; failed publication leaves a queued job. Celery beat recovers committed jobs after a ten-second grace period. `FOR UPDATE SKIP LOCKED` prevents concurrent processing. A real queued job survived an initial worker import failure and completed after the corrected worker restarted. Broker-outage recovery is implemented but a deliberate Redis outage was not tested in the shared running stack. Large-load, long-running lease, multi-host package sharing, and scale testing remain outstanding. Each app stack needs shared package storage if jobs may run on a different machine; RDS alone does not share ZIP files.

The gateway signs the authenticated display name, email and observed network address into the internal assertion. Browser-selected identity/IP headers are not trusted. Records distinguish request, packaging, and delivery-start time. Delivery start does not prove that a browser received the entire file. Docker/proxy addresses may appear; genuine upstream client attribution requires an explicitly trusted proxy deployment, not accepting arbitrary X-Forwarded-For.

Administrator Downloads now includes local-file watermark upload. The API independently requires admin permission. Authenticated signal-only identifiers also resolve stored records; conflicting metadata/signal identities withhold attribution. Historical records may lack names, actual addresses or delivery time; those values are reported as missing. A valid watermark associates an identifier with a package, not proof of uploader identity or unchanged content.

## Format policy and verified limits

No watermark is invincible. Metadata can be removed or copied; signal carriers can be destroyed by sufficiently strong transformations. Signal methods alter samples/coefficients, whereas metadata/sidecar methods avoid those signal changes. No downstream training run or adversarial robustness certification was performed.

| Format | Current integrated method | Verification / limits |
|---|---|---|
| JPEG/JPG/JFIF | Native DCT coefficients + HMAC metadata | Baseline/progressive/grayscale fixture recovery, coefficient invariants, PSNR >35 dB; real S3 JPEG full workflow passed. Small images may lack capacity. |
| PNG8 L/LA/RGB/RGBA | Haar DWT + block DCT + metadata | Recovery after metadata removal, alpha preserved, fixture PSNR >40 dB. |
| Palette PNG | Expand palette to truecolor, DWT+DCT + metadata | Recovery and fixture PSNR >40 dB. Palette encoding itself changes. |
| Animated PNG8 | DWT+DCT on composited frames + metadata | Tested two frames, timing, loop, alpha and authenticated recovery; wider animation/disposal combinations not certified. |
| Static PNG16 grayscale/color/alpha | Precision-preserving DWT+DCT + metadata | 16-bit samples and alpha retained, recovery and fixture PSNR >40 dB. PNG16 animation is explicitly unsupported. |
| BMP, TIFF8, lossless WebP | DWT+DCT pixel signal; no separate token | Format/geometry/alpha checks and fixture PSNR >40 dB. Lossy WebP is rejected in signal mode. Unusual TIFF scientific modes require separate validation. |
| WAV, FLAC | STFT + metadata | PCM/float fixtures, recovery after lossless conversion and gain change, SNR >35 dB. Mono/stereo, 16–96 kHz, at most 10 million channel samples; quiet/short/no-headroom sources may fail. |
| MP3 | Patched native LAME MDCT + metadata | Mono/stereo fixtures passed authenticated recovery and >25 dB watermark-only SNR versus matched encode. Re-encoding itself introduces additional codec loss. |
| AAC/M4A | Patched native AAC MDCT; signal identifier | ADTS/M4A fixtures passed, >25 dB watermark-only SNR, metadata-stripping remux recovery. AAC-LC, mono/stereo 44.1/48 kHz, at most 120 seconds. |
| MP4/MOV/M4V/MKV H.264/H.265 | Native coefficient watermark; signal identifier | H.264/H.265 MP4 fixtures passed recovery, decode, audio packet preservation, remux and >30 dB PSNR. Native path is experimental all-intra re-encoding: 8-bit YUV420, <=1080p, constant <=30 fps, <=12 seconds. Other listed containers and real NAS videos still need coverage. |
| PDF | PDF metadata token | Parser roundtrip preserves page count and token; no signal watermark. Encrypted PDFs rejected. Existing PDF signatures are not preserved by modification. |
| CSV/JSON/text, Office files, GIF/HEIC/SVG and other unsupported files | Unchanged original plus signed `.watermark.json` sidecar | Original bytes preserved. Upload the sidecar to trace it. An unsupported original alone cannot identify its downloader. This intentionally replaces unsafe arbitrary text appended to training data. |

Signal inputs have a 64 MiB bound; image transforms have a 16-million-pixel aggregate bound. Download source limits remain 128 MiB per file and 2 GiB per batch. Failing a configured signal method fails the package with an error; it does not silently claim a watermark was applied. Metadata-only flags remain available for workloads outside these experimental bounds.

Additional formats to consider: OGG/Opus and AIFF (container tags or sidecars; signal needs separate validation), WebM/VP9/AV1/AVI (container metadata where verified, otherwise sidecars; no current native coefficient implementation), JPEG XL/AVIF/RAW and scientific/DICOM images (prefer unchanged samples plus sidecars until precision and domain effects are tested), Parquet/Arrow/HDF5 (format-specific metadata or sidecars). Do not apply natural-image pixel changes to scientific/medical data without task-specific evaluation.

## Validation evidence

- Frontend: 17 tests passed; production build passed (existing mixed-import chunk warning only).
- NAS/auth/source access: 24 focused tests passed, including isolated SMB identities, subfolder scoping, bounds and traversal rejection. Network authentication remains blocked as above.
- Gateway: 30 contract tests passed.
- Watermarks/tracker: 34 tests passed, including PNG16 color/alpha, animation, unsupported-byte preservation, PDF metadata, JPEG, audio, signal/metadata conflicts and admin authorization.
- Compiled native codecs: 11 tests passed, none skipped (MP3, AAC/M4A, H.264/H.265 and standalone adapter tests). These are controlled fixtures, not real NAS acceptance.
- Live dispatch: one-file direct, three-file Celery, and busy one-file Celery fallback passed ZIP validation and stored provenance; forged browser identity/IP headers were ignored. Jobs `ca40f8eb-2b76-44b9-8bc5-566021acd040`, `c090a473-61c1-41b9-8424-4706a03e80ff`, `45e69be8-73e9-465e-94bd-4e81fe34a0e0`. This dispatch test ran before enabling signal flags; signal transformations are intentionally queued.
- Active signal profile: real ABO JPEG job `fc2aa282-e0fb-4be5-aab9-73a7b5902419` completed via Celery; ZIP, metadata signature, signal authentication and persistent trace all passed.
- Browser: administrator local-file upload matched a real record; standard-user UI hid the tracker and direct API upload returned 403. Desktop/mobile screenshots saved under ignored `.integration/`.
- Explicit additive RDS migration 2 applied twice without record-count changes: 20 existing download jobs, 92 forensic records, 25 identity users preserved. No shared samsungdb schema changes. This does not substitute for every historical deployment's upgrade test.

## Setup and recovery

Build the base integration runtime first, then `deploy/integration/Dockerfile.download`, then `deploy/integration/Dockerfile.download-native`. Native sources are pinned/checksummed by the existing build scripts; build tools stay in an intermediate image. Runtime binaries live under `/opt/nexus-native`, outside the read-only source bind mount.

Normal Compose starts the dedicated download image. To activate the compiled profile, use `DOWNLOAD_IMAGE=smsprsm-integration-download-native:local`, set the four watermark flags (`JPEG_CODEC_WATERMARK`, `LOSSLESS_SIGNAL_WATERMARK`, `NATIVE_AUDIO_WATERMARK`, `NATIVE_VIDEO_WATERMARK`) to true, and supply a stable `CODEC_WATERMARK_SECRET` of at least 32 bytes. The alternative `watermark.yml` override selects the same profile. API and worker must share both watermark secrets. These settings are active locally in ignored `.integration/stack.env`; no secrets are committed. Preserve keys for historical extraction.

Before restarting the API/worker on an existing installation, run `services/download/integration_migrations.py` in the download working directory with the correct database environment. It adds nullable provenance columns and records migration 2 without rewriting historical records. The full integration migrator also invokes it.

Run exactly one Celery beat scheduler per shared download database/queue. Keep Redis persistence enabled, retain the package volume, and restart the download worker to recover committed building jobs. A future multi-host deployment needs a common broker, package storage and compatible watermark keys; separate local brokers do not form a single shared work queue. Never delete Redis/database/package volumes as a routine recovery step.
