# Download request details

Download results, Download Selected and Download Object open the same dialog. It shows the dataset(s), available file count and source size, editable download count, estimated ZIP size, average source bytes, optional metadata CSV, required project name and purpose, server date and the earliest selected licence expiry. Mixed expiries are labelled. ZIP size is a source-size estimate; the delivered compressed size is only known after packaging.

`POST /downloads/batch` now requires nonblank `project_name` (200 characters maximum) and `usage_purpose` (2000 maximum), alongside `file_ids`. Optional fields are `include_metadata_csv` (defaults to true), `source_context`, `displayed_available_count`, and `displayed_available_bytes`. Existing API clients must supply the two required fields. The displayed availability values are a client snapshot of the preview, not an authorization or size-limit input. Selected counts, bytes, datasets, date and licence dates are recalculated by the server. `POST /downloads/preview` accepts file IDs and returns these facts after the same current-access check used for downloads.

The `download.document_download_jobs.request_details` JSON stores the complete request snapshot, including failed jobs. Each packaged file's `download.forensic_audit_logs` row stores `job_id` and the same `request_details`, beside its existing token, signature, recipient and file ID. The signed watermark includes a SHA-256 digest of this snapshot and the job ID, without embedding the project and purpose text into the distributed file. Existing records remain nullable rather than receiving invented historical values. Download history shows project and purpose; the administrator watermark tracker returns these details for matched files.

Each archive part has `SHA256SUMS.txt` for the delivered, watermarked files, sidecars and manifest. When enabled, `metadata.csv` contains filename, document ID, title, tags, category, width, height, source bytes, dataset and licence expiry, and is also covered by the checksums. CSV text is protected against spreadsheet formula interpretation. Per-part manifests and CSV contain only files in that part.

Before restarting an existing download API/worker, run `python integration_migrations.py` from `services/download` inside the configured download container. This applies additive download migration 3; preserve existing tables and volumes. Build the frontend and restart Search to expose the additional `available_bytes` download-plan field.

Verification: frontend contract tests, search-plan tests, archive/CSV/checksum and required-field tests, and database round-trip tests. A live popup request on 23 September 2026 produced job `33c9509d-d45a-4382-9922-920775b59d97`; its saved request and forensic row matched, the signed snapshot digest verified, and every archive checksum matched its delivered bytes.


## Transfer progress and limits (23 September 2026)

The download-specific per-file ceiling is removed. `limits.max_file_bytes = 0` means unlimited; the legacy environment variable no longer reintroduces the 128 MB exclusion. Search planning and preview retain all source files, in ranking/selection order. Whole-request count/byte and disk-space checks still apply. Format-specific watermark requirements (supported codecs, dimensions, duration, valid lossless sources, etc.) still apply; these are not download selection limits.

Originals stream to temporary disk and ZIP entries can stream from disk. Native video uses a file-based watermark path without the old in-memory input cap, and authenticates the recovered watermark before publishing. Sidecar formats also avoid buffering entire originals. Other existing watermark methods retain their format-specific processing constraints.

All three download entry points and Downloads history use the same save controls. Supporting browsers ask for a destination via `showSaveFilePicker` before starting the authenticated transfer, and write chunks directly to the chosen file. Cancellation or incomplete responses abort the writable file. Browsers without that API use their normal download handler with a visible explanation of how to enable a save prompt. Their completion message says handed to browser, rather than claiming disk-save completion.

Transfer progress includes bytes received, rolling three-second transfer rate, estimated remaining time, and elapsed time. Completed transfers show filename, bytes, elapsed time, average rate, completion date/time and part number. Receipts survive navigation/reloads in the same browser session; they are not server audit records and do not contain a local filesystem path. Preparation time (queue + packaging) is shown separately from transfer time. Its ETA is based on average files prepared, so heterogeneous files can make it fluctuate.

Search results display client request-to-response duration in seconds (includes network and JSON parsing; excludes typing debounce and thumbnail loading), plus the server's measured execution time in milliseconds. Sliders clamp the dragged bound to its counterpart without moving the other slider.

Diagnosis: latest failed jobs stopped on `responsible-dog-care-guide.pdf` from `NAS-First_attempt`; the NAS SMB connection was unreachable from the running app. Source failures now identify the file and advise checking source storage/access. Reconnecting source storage is still required; no source-availability fix is claimed.
