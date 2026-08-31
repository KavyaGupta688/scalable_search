# AI Data Platform: Download & Metadata Watermarking Gateway
### High-Performance S3 Ingestion, Zero-Pixel Watermarking, Celery + Redis Async Tasks & PostgreSQL Forensics

High-performance, secure "last-mile" data delivery gateway designed for large-scale enterprise data repositories (up to 4 TB scale). Injects tamper-proof cryptographic tracking tokens directly into file metadata headers with **0% pixel alteration**, non-blocking background queueing via **Celery & Redis**, and forensic audit storage in **PostgreSQL**.

---

## 🌟 Core Highlights

- **0% ML Pixel Distortion**: Direct binary header manipulation (PNG `tEXt` chunk / JPEG `COM` segment) without decompressing or re-encoding image pixel matrices. Downstream ML data loaders (`cv2`, `PIL`, `PyTorch`) load 100% clean data.
- **$O(1)$ Memory Stream Processing**: Handles multi-gigabyte files and petabyte datasets via `boto3` chunked generators without loading large files into server RAM.
- **Celery + Redis Background Task Queue**: Non-blocking asynchronous downloads, multi-file batching, and ZIP packaging with real-time percentage progress tracking.
- **PostgreSQL Forensic Database**: Persistent, indexed audit logs recording every watermark token, downloading user, IP address, timestamp, and S3 key.
- **Survives File Renaming**: Forensic inspection tool traces data leaks even if the file is renamed (e.g. `dataset_01.jpg` $\rightarrow$ `confidential_leak.jpg`).
- **Cryptographic Anti-Tamper Signatures**: HMAC-SHA256 tokens linking `User ID`, `Download UUID`, `S3 Key`, `Timestamp`, and `IP`.

---

## 🚀 Quickstart & Execution

### 1. Initialize PostgreSQL Database
```bash
python scripts/setup_postgres.py
```

### 2. Start Celery Worker (Optional for Redis Queue)
```bash
celery -A core.celery_app.celery_app worker --loglevel=info --pool=threads
```
*(Note: If Redis/Celery worker is offline, the gateway automatically falls back to non-blocking inline execution without breaking the user experience).*

### 3. Launch the Gateway Server & Web Dashboard
```bash
python api/server.py
```
Open your browser at: **`http://127.0.0.1:8000`**

---

## 🛠️ Automated Verification & Test Suites

### Run All Security, Zero-Pixel & Anti-Tamper Tests:
```bash
python tests/test_integrity.py
```
*Asserts mathematical 0.000% pixel distortion, HMAC tamper rejection, JPEG/PNG injection, and renaming resilience.*

### Run PostgreSQL & Celery Async Integration Tests:
```bash
python tests/test_postgres_celery.py
```
*Validates live PostgreSQL connection, ORM schema creation, Celery background batch processing, and ZIP package token verification.*

---

## 🔍 Forensic Leak Verification via CLI
```bash
# Inspect any downloaded or suspect file
python cli/forensic_verify.py path/to/suspect_image.png
```

---

## 🐘 IDE & PostgreSQL Connection Details

| Parameter | Value |
| :--- | :--- |
| **Host** | `localhost` (or `127.0.0.1`) |
| **Port** | `5432` |
| **Database** | `watermark_db` |
| **Username** | `postgres` |
| **Password** | `postgres` |
| **Connection String** | `postgresql://postgres:postgres@localhost:5432/watermark_db` |

### Key Tables in PostgreSQL:
1. `forensic_audit_logs`: Records every watermarked file delivered (`download_id`, `user_id`, `user_email`, `s3_key`, `timestamp`, `client_ip`, `token_str`, `token_signature`, `status`).
2. `async_download_jobs`: Tracks Celery asynchronous packaging jobs (`job_id`, `user_id`, `s3_keys_json`, `total_files`, `status`, `progress_pct`, `output_filename`).

---

## 📁 Directory Structure

```
watermark_gateway/
├── config.py                 # S3 credentials, HMAC secret keys, Redis, PostgreSQL settings
├── database/
│   ├── models.py             # SQLAlchemy ORM models (ForensicAuditLog, AsyncDownloadJob)
│   └── db.py                 # PostgreSQL connection manager & query layer
├── core/
│   ├── crypto.py             # HMAC-SHA256 token generator & validator
│   ├── celery_app.py         # Celery configuration with Redis broker
│   ├── tasks.py              # Celery background tasks (S3 download, watermarking, ZIP)
│   ├── s3_client.py          # Boto3 chunked S3 streaming handler + simulator
│   └── injectors/
│       ├── png_injector.py   # Pure-byte PNG tEXt chunk injector
│       ├── jpeg_injector.py  # Pure-byte JPEG COM/APP1 segment injector
│       └── extractor.py      # Multi-format forensic metadata extractor
├── api/
│   ├── routes.py             # REST & Streaming endpoints (/download, /async, /verify)
│   └── server.py             # FastAPI entrypoint
├── cli/
│   └── forensic_verify.py    # Forensic CLI: Inspect any leaked file
├── frontend/                 # Interactive Dashboard UI (Dark Mode / Glassmorphism)
├── scripts/
│   └── setup_postgres.py     # PostgreSQL auto-initializer
├── tests/
│   ├── test_integrity.py     # Automated ML zero-pixel distortion test suite
│   └── test_postgres_celery.py # Celery & PostgreSQL integration tests
├── docker-compose.yml        # PostgreSQL, Redis & Celery Docker stack
├── Dockerfile                # Container deployment file
└── requirements.txt          # Pinned project dependencies
```
