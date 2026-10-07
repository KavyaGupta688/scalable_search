# Search scalability changes

This page covers what changed in the Search module (S1–S9 of report section 7.11), how to
roll it out, and the limits that still apply. Every change is backward compatible. With
no new configuration, Search returns the same results in the same order as before. The
only exception is that a broad vector query used to fail with a 422 error and now returns
results.

## What changed

| # | Change | Where | Effect on results |
|---|--------|-------|-------------------|
| S1 | **Licence gate without the 100k limit.** Up to `VECTOR_EXACT_GATE_MAX` visible ids are still sent to Qdrant as an exact `HasId` list. For larger sets, Qdrant filters on payload fields, over-fetches ×`VECTOR_OVERFETCH`, and SQL checks every hit on the primary. Filter sets known to be large skip the id read for 5 minutes. The Qdrant filter also excludes points whose `license_status` is not `active` (`must_not`, so points without the field still pass). | `vector_search_service.py`, `utils/filters.py` | Identical up to the gate. Above it, results stay correct (every hit is SQL-verified), but recall depends on HNSW. The 422 error is gone. |
| S2 | **Full-text prefilter.** A `search_vector` tsvector is kept by a trigger, has a GIN index, and is used as a prefilter that keeps every row the existing regex would match. The regex still decides matches and `_score` still ranks. It is enabled only when the column and trigger exist (`SEARCH_FTS_PREFILTER=false` turns it off). | `file_repository.py`, `query_normalizer.term_variants`, `scripts/migrate_integration.py` | Identical. Fewer rows are scanned. |
| S3 | **Lightweight candidates.** Text mode reads one page instead of 200+ rows. The download plan in text mode reads only `(id, size)`. The duplicate `COUNT` queries are removed. | `search_service.py`, `file_repository.py` | Identical, including global `keyword_rank`. |
| S4 | **Redis caches** for hybrid rankings and facet counts (`SEARCH_CACHE_TTL_SECONDS`, default 60). Keys include `search:catalog_version`, which the indexer increments after every projection. Cached rankings are reloaded through the SQL visibility gate. | `services/search_cache.py`, `modules/shared/indexer.py` | Identical. A catalogue change invalidates entries straight away. |
| S5 | **Qdrant layout from the environment:** shards (6), replication, HNSW m16/ef_construct 128, `hnsw_ef` 128 per query, optional int8 quantisation with rescoring, and gRPC. **Alias-aware** everywhere (indexer, AI worker, observability), plus an alias migration that copies points without re-embedding them. | `modules/shared/vector_store.py`, `scripts/migrate_vector_collection.py` | Same results. `hnsw_ef` 128 is the default for this collection size. |
| S6 | **Graceful degradation.** If vector retrieval fails or times out (`VECTOR_TIMEOUT_SECONDS`), hybrid search answers from keywords. A circuit breaker skips Qdrant for 30 s after 5 failures. If the reranker fails, results fall back to strict all-terms matching. The response carries `partial_results` and `degraded_components`, and the UI shows a notice. Partial answers are never cached. `QDRANT_EMBEDDED` is removed. | `hybrid_search_service.py`, `schemas/search.py`, `frontend/src/components/SearchTiming.jsx` | Normal operation is unchanged. During an outage, results are narrower and labelled as partial. |
| S7 | **PgBouncer and read replica.** `DB_STATEMENT_CACHE_SIZE=0` makes connections safe for transaction pooling. `DATABASE_READ_URL` sends keyword ranking and facets to a replica. The returned page is always re-checked on the primary, and licence checks never use the replica. | `db/postgres.py`, `core/dependencies.py` | Identical. Replica lag can delay a new document by the lag time, but never shows a revoked one. |
| S8 | **Shared embedding cache** in Redis (CLIP and MiniLM query vectors, keyed by model) behind the in-process LRU. **Prometheus `/metrics`** on every replica, a DNS scrape job, and alerts for latency, degradation, the payload path and cache hit rate. | `clients/embedding_client.py`, `core/metrics.py`, `deploy/integration/monitoring/` | Identical. Vectors are rounded to float32 on both a cache hit and a miss. |
| S9 | **Horizontal replicas.** Search is stateless; `search-scale.yml` runs `SEARCH_REPLICAS` copies, a three-node Qdrant cluster and PgBouncer. | `deploy/integration/search-scale.yml`, `deploy/integration/pgbouncer/` | — |

### Follow-up fixes

| Fix | Where | Effect |
|-----|-------|--------|
| **Cache entries end at the next licence expiry.** An entry lives for at most `SEARCH_CACHE_TTL_SECONDS`, and never past the earliest active `expires_at` after the moment its computation started. This uses one indexed lookup (`idx_entitlements_expiry`), reused until the catalogue changes, that expiry passes, or 30 s go by. If a licence expired during the computation, or the lookup fails, the entry is not cached. | `services/search_cache.py` | Cached counts are always exact. |
| **Adaptive fetching.** On the payload path, if too few hits pass the SQL check, the next batch is fetched, up to `VECTOR_MAX_ROUNDS` (5). A full first batch costs one round, as before. | `vector_search_service._fetch_verified` | Broad searches fill their window instead of coming back short. |
| **Exact vector totals.** On the payload path, `search_by_vector` reports Qdrant's exact count for the same filter. | `vector_search_service.py` | The total equals the visible count whenever payloads are current. |
| **Shared relevance scores.** Cross-encoder pair scores are shared through Redis (`search:rel:<model revision>:<sha256>`, 1 day). Every replica computes each pair at most once. | `services/relevance_service.py` | Identical scores (the model is deterministic). Less CPU. |
| **Trigram prefilter for other scripts.** A `pg_trgm` GIN index over all keyword fields joined by spaces (`SEARCH_DOCUMENT_SQL`). PostgreSQL applies it to the same whole-term regex for terms the full-text vector skips. It is built by the migration if `pg_trgm` is available (`SEARCH_TRIGRAM_INDEX=false` skips it) and detected at startup. | `file_repository.fts_prefilter`, `scripts/migrate_integration.py` | Identical results; non-ASCII terms of 3 or more characters are index-backed. |

### Changes in other modules

- **Ingestion (retention):** when licences expire, the same transaction enqueues a
  `search-refresh` delivery for each affected document. The outbox worker re-projects
  the document, so Qdrant's `license_status` follows the licence.
- **Indexer:** writes `license_status`, `file_size` and `long_edge` to both collections,
  and increments the catalogue version after every projection.
- **AI worker, observability, migration:** look collections up through aliases. The
  migration also indexes the semantic collection's payload fields.
- **Facets:** entries with equal counts are now ordered by value. Before, their order was
  undefined, so the top-15 tag list could differ between replicas.

## Rollout

1. Deploy the code. No configuration is needed and results are unchanged.
2. Run `python scripts/migrate_integration.py`. It adds `search_vector`, the trigger, the
   batched backfill, both indexes (built `CONCURRENTLY`) and the semantic payload indexes.
   Search detects the prefilter at startup.
3. Run `python scripts/reindex_search_payloads.py`, then set `QDRANT_EXTENDED_PAYLOAD=true`
   so that size and resolution filters also run inside Qdrant.
4. Optional: scale out with `docker compose -f compose.yml -f monitoring.yml -f search-scale.yml up -d`.
   Copy `pgbouncer/userlist.txt.example` to `userlist.txt` first.
5. Optional: change the Qdrant layout of an existing collection, in a quiet period:
   `python scripts/migrate_vector_collection.py --target semantic --switch`. The first run
   on a physical collection also needs `--delete-source`.

## Validation done

- Unit tests: `app/tests/test_search_scalability.py`, plus the existing scaling,
  embedding, resolution, retention, observability and repository-level suites. All pass.
  Tests that need `torch`, the acceptance catalogue or Qdrant were not run.
- On PostgreSQL 16, under both `C` and Windows locales:
  - The migration DDL runs and can be re-run.
  - Backfill, the trigger on update, the oversize-text NULL fallback and use of the GIN
    index all work.
  - No regex match was missing from the full-text prefilter, over 3,000 adversarial rows
    and 47 terms.
- On PostgreSQL 16.10 with `pg_trgm`, after the follow-up fixes: 51 queries (English,
  German, French, Russian, Hindi, Japanese, mixed) × 4 filter sets × AND/OR. With the
  prefilters off and on, all 576 result sets were byte-identical. The trigram index was
  used for Latin and Cyrillic terms of 3 or more characters. The cache lifetime was cut to
  24 s for a licence expiring in 25 s.
- Earlier run: on PostgreSQL with 2,500 documents, 23 queries × 4 filter sets × AND/OR, the prefilter
  off and on gave byte-identical keyword results, totals, pages, download plans and
  facets (368/368). Paged text mode and the slimmer download plan were identical to the
  old full-row paths.
- An API smoke test against PostgreSQL passed with and without a read replica and
  `statement_cache_size=0`: `/search` (text), `/search/text`, `/search/facets`,
  `/search/download-plan`, `/health` and `/metrics`.

## Limitations

**Accuracy and completeness**

1. **Vector recall above the exact gate is approximate.** Every hit is SQL-verified,
   and adaptive fetching refills the window, but HNSW with payload filters can still miss
   some neighbours. Raising `QDRANT_HNSW_EF` trades speed for recall.
2. **Vector totals on the payload path** count Qdrant points matching the filter. This
   equals the visible count whenever payloads are current.
3. **Hybrid and vector modes cap each branch at 200 candidates** (`VECTOR_CANDIDATES`), as
   before. Only text mode is exhaustive, so download plans larger than the candidate
   window should use text mode.
4. **Size and resolution filters run only in SQL** until `reindex_search_payloads.py` has
   run and `QDRANT_EXTENDED_PAYLOAD=true` is set. Until then, a selective size filter on a
   very large catalogue can reduce vector recall (see 1).
5. **Pure vector mode has no keyword fallback.** It still returns 503 when Qdrant is
   down, by design; only hybrid mode degrades.

**Performance**

6. **The prefilters do not help every term.** Terms shorter than 3 characters in
   non-Latin scripts (for example `大阪`) cannot use a trigram index. Neither can scripts
   the database locale does not classify as letters (Hindi under a Windows locale; any
   non-ASCII text under the `C` locale). Without `pg_trgm`, non-ASCII terms use the regex
   scan. Very common terms prune little, and rows whose text is too large for a tsvector
   (over 1 MB) are always regex-scanned. Results are correct in every case.
7. **The cross-encoder reranker is the main per-query CPU cost** (up to about 400
   pairs). Shared pair scores help repeated passages only. High QPS needs GPU workers, or
   a quantised model evaluated against the test queries.
8. **Each replica loads CLIP, MiniLM and the cross-encoder** (about 1–2 GB), so replicas
   scale throughput at a memory cost.

**Freshness and consistency**

9. **Cache lifetime depends on PostgreSQL being reachable.** If the next-expiry lookup
   fails, results are simply not cached.
10. **Qdrant's `license_status` follows SQL asynchronously** through the outbox, usually
    within seconds. Any future path that re-activates a licence must also enqueue
    `search-refresh`; otherwise the document stays filtered out of vector results that
    use payload filtering.
11. **With a read replica, new documents can appear only after the replica catches up.**
    A page can briefly be shorter than `limit` when replica rows fail the primary check.
12. **Redis is a soft dependency.** With `REDIS_FALLBACK_MEMORY=true`, the result,
    facet and embedding caches are off.

**Operations**

13. **Alias migration.** The first switch of a physical collection has a short gap in
    which requests fail. Writes made during the copy rely on the catch-up pass, so run
    it in a quiet period. The shard count is fixed once a collection is created.
14. **The infrastructure files have not been run.** `search-scale.yml`, the PgBouncer
    config and the per-replica DNS scraping were written but not tested, because Docker
    was unavailable. PgBouncer must be 1.20 or later for `track_extra_parameters`; check
    the image tag. Clients connect through Qdrant node 1.
15. **The trigram index costs space and write time:** roughly the size of the keyword
    text, plus slower inserts.
16. **Not run locally:** the integration suites (acceptance catalogue, Qdrant) and tests
    that need `torch` or `pymupdf`. Run them in CI before merging.
