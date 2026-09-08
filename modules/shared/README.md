# Shared

Cross-cutting interfaces used by the feature modules.

```text
shared/
  auth/         SSO, bearer-token, and RBAC interfaces
  contracts/    API request/response schemas and shared enums
  audit/        activity event types and audit publisher interface
  storage/      private object-storage interface
  search/       text/vector search provider interfaces
```