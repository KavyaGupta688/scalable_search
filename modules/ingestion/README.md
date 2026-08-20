# Ingestion

Owns file intake through indexing, including validation, checksum verification, metadata registration, preview generation, and embedding requests.

```text
ingestion/
  api/           upload and ingestion-status endpoints
  application/   ingestion pipeline orchestration and retryable jobs
  domain/        ingestion records, file metadata, and processing states
  infrastructure/storage, metadata, media processing, and queue adapters
  workers/       background processing entry points
  tests/         unit and pipeline contract tests
```

Ingestion exposes registered file records and processing events to the other modules through contracts.