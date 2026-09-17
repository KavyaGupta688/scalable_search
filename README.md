# Download and forensic watermark gateway

A Python/FastAPI prototype that downloads S3 assets, associates them with an
authenticated download ID, and looks up that ID during forensic inspection.
The dashboard supports browsing, downloads, ZIP batches, background jobs and
verification. SQLAlchemy stores audit/job records in PostgreSQL/RDS with a SQLite
fallback; Celery uses Redis for queued packaging.

Metadata tokens remain available. Experimental signal watermarks now cover JPEG
DCT, PNG DWT-DCT, WAV/FLAC STFT, native MP3/AAC MDCT, and native H.264/H.265
coefficients. Signal watermarking changes the media. Metadata-removal recovery is
tested; zero training impact and general attack resistance are not claimed.
See [codec setup, evidence and limits](CODEC_WATERMARKING.md).

## Run locally

    python3 -m venv .venv
    .venv/bin/pip install -r requirements-codec.txt
    # Configure .env using .env.example: S3, database and private keys.
    .venv/bin/python api/server.py

Open http://127.0.0.1:8000. USE_MOCK_S3=true creates local demo assets.
Native MP3/AAC/video modes additionally require the source builds documented in
[CODEC_WATERMARKING.md](CODEC_WATERMARKING.md). Signal modes default to off; enable
them explicitly after configuring a private key.

For queued packages, run Redis and a worker:

    .venv/bin/celery -A core.celery_app.celery_app worker --loglevel=info --pool=threads

The existing broker-error fallback executes synchronously. It does not replace
Redis/workers and does not reliably detect an offline worker when the broker is
reachable. Native modes are bounded prototypes, not a validated multi-terabyte
streaming system.

## Verification

    .venv/bin/python -m pytest tests -q
    .venv/bin/python cli/forensic_verify.py suspect-file

Tests use development keys and mocked cloud/database services. Full native tests
require requirements-native-build.txt and the pinned source builds. The local
signal tool can embed/extract without S3; see cli/signal_watermark.py --help.

## Code layout

- api/: download, job, health, audit and verification endpoints.
- core/injectors/: format routing and metadata insertion/extraction.
- core/codec_jpeg.py and core/signal_*.py: JPEG and decoded-data signal methods.
- core/native_*.py and native/: isolated codec adapters and native source hooks.
- scripts/build_native_*.py: reproducible local native builds.
- database/: audit and job persistence.
- frontend/: browser dashboard.
- cli/: forensic and signal tools.
- tests/: recovery, compatibility, quality and integration checks.

The project still needs production authentication/authorization, operational
hardening and representative media/model evaluation. A signed ID supports tracing
a recorded download; it does not conclusively identify a person who leaked a file.
