# Validation commands for the AI branch update

Run from the repository root, using the existing approved RDS runtime. These commands were executed on 20 September 2026. Detailed outcomes and limits are in INTEGRATION_REPORT.md.

## Module checks

```powershell
docker exec smsprsm-rds-ai-1 python -m pytest -p no:cacheprovider modules/ai_tag_description_generation/tests tests/integration/test_whisper_loader.py -q
docker exec smsprsm-rds-gateway-1 python -m pytest -p no:cacheprovider tests/test_integration_api.py services/ingestion/tests -q
```

Results: 26 AI/loader tests plus 8 subtests; 54 Gateway/Ingestion tests. Frontend `npm test` passed 14 tests and `npm run build` passed. No frontend lint/type-check script exists.

The Download suite ran in a disposable `docker compose run --rm --no-deps` container, with its pinned `services/download/requirements-codec.txt` installed before `python -m pytest -p no:cacheprovider tests -q`. Result: 28 passed, 11 skipped for absent patched native binaries. The live Download container was not modified.

## Isolated database checks

`tests/integration/legacy_upgrade.py` created `legacy_acceptance_dd84a28b` on the approved RDS instance. It applied ingestion 004, inserted constructed legacy authentication/forensic/download/Audit records, upgraded through 014, applied AI through 004 and ran full migration twice. Ownership and record preservation assertions passed. Audit's `tests/test_audit_extended.py` passed 2 tests with both database URLs redirected to this temporary database.

The migration used a separate Qdrant collection, `integration_validation_eb7ab443dc`. Then:

```powershell
docker exec smsprsm-rds-search-1 python /app/tests/integration/pii_publication.py legacy_acceptance_dd84a28b integration_validation_eb7ab443dc
```

The policy checks passed, followed by 11 Search tests. The script restricts resource names and overrides database/collection settings before importing application code. It deliberately seeds synthetic model outputs only there. Both temporary resources were removed afterward. To reproduce, create fresh names through the legacy helper and pass the actual generated names; do not reuse the now-deleted resources or substitute application database names.

## Actual source and browser checks

```powershell
docker exec smsprsm-rds-ai-1 python tests/integration/rds_actual_workflow.py 917ab86f-89fb-49ee-b1a0-7f3f54edf2d3 --expected-documents 6
node tests/integration/rds-browser.cjs
```

Both passed; the browser requires Playwright and Edge. No model adapters or synthetic catalog rows were substituted. It creates normal test users, downloads and Audit events. The browser-only outage interception checks explicit errors; all other requests use real services. Eleven browser groups passed with no page errors. Ignored reports/screenshots are in `.integration/rds-browser/` and `/models/provisioning/actual-workflow.json`.

## Final checks

Focused Ruff (`--no-cache --select E9,F63,F7,F82`) passed on all changed Python files, including the new publication helper and isolated regression script. `git diff --check` passed. Gateway `/ready` returned 200 with Ingestion, Search, AI and Download all ready. Ingestion and enrichment had zero undelivered outbox records. The regenerated Word guide was rendered and all 10 current pages visually inspected.

Earlier broker-outage, duplicate-delivery, missing-model, forged-identity and ownership recovery tests remain separately documented historical results. They were not rerun as destructive stress tests against the current RDS application in this update.
