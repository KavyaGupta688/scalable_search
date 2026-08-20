# Modules

The platform is split into four independently owned modules. Each module keeps its API, application logic, domain models, and infrastructure adapters together.

## Modules

- `ai_tag_description_generation`: generates and manages AI-produced tags and descriptions.
- `searching`: handles keyword, natural-language, vector, similar-file search, facets, ranking, and previews.
- `ingestion`: validates, registers, processes, and indexes uploaded files.
- `download_auditing`: handles selective downloads and audit visibility for platform actions.

The `shared` directory contains cross-cutting contracts and adapters. Modules should depend on shared interfaces, not on another module's infrastructure implementation.