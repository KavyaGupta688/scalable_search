# AI Tag And Description Generation

Owns asynchronous generation of tags and descriptions from ingested file content and metadata.

```text
ai-tag-description-generation/
  api/           HTTP handlers and request validation
  application/   generation orchestration and job use cases
  domain/        generation jobs, prompts, and result models
  infrastructure/embedding/model providers and persistence adapters
  tests/         unit and integration tests
```

Generation should publish results through module contracts and must not write directly to search indexes.