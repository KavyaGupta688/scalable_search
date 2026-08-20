# Searching

Owns keyword, natural-language, vector, similar-file, facet, preview, and ranked-result workflows.

```text
searching/
  api/           text, vector, similar, facets, and file-preview endpoints
  application/   query normalization, retrieval planning, and result assembly
  domain/        search requests, filters, result ranking, and facets
  infrastructure/text, vector, metadata, and reranking provider adapters
  tests/         unit and API contract tests
```

The module consumes shared search and metadata interfaces. It never accesses PostgreSQL or Qdrant directly from the API layer.