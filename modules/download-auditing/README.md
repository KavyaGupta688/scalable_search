# Download And Auditing

Owns selective batch-download creation, download status tracking, and audit visibility for searches, previews, downloads, and other governed actions.

```text
download-auditing/
  api/           download, status, and audit-log endpoints
  application/   ZIP orchestration, authorization, and audit use cases
  domain/        download jobs, audit events, and status models
  infrastructure/storage, audit persistence, queue, and notification adapters
  workers/       ZIP-build and cleanup entry points
  tests/         unit and API contract tests
```

Private storage paths stay behind the shared storage interface. Authorization and expiry checks happen before a download is built.