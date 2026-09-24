# Search relevance

## Changes

RRF values such as 0.0083 are rank-fusion scores, not calibrated probabilities. User and admin results now show matching evidence (Keyword match, Semantic match, or both), while the API retains raw diagnostic scores.

Exact Keyword retrieval requires every meaningful query term, matched as a whole word with plural support. Hybrid retrieval also admits partial lexical candidates for subsequent relevance verification, improving recall for natural phrases. This prevents `ball` matching `balloon` and `red ball` matching a file containing only `red`. All keyword-derived facets use the same conditions. Partial prefixes still work in suggestion code; completed searches require whole terms.

Hybrid and semantic search retrieve a bounded CLIP candidate window, then verify query/document relevance locally using `cross-encoder/ms-marco-MiniLM-L6-v2`, pinned to revision `ce0834f22110de6d9222af7a7a03628121708969`. Generic CLIP neighbours no longer qualify merely by being near the best neighbour. The verifier evaluates up to three passages per file: primary descriptive text plus query-bearing windows from descriptions, captions, OCR and transcripts. It can therefore find terms late in long extracted text. Generated summary text is used only when no description/caption exists, and tag lists never independently qualify a match. `RELEVANCE_MIN_LOGIT` defaults to -3.0, calibrated against the current sample catalog; it is not a probability. Whole-term title/filename matches are retained. Short queries can also qualify through explicit descriptions/captions; this avoids the question-answering model rejecting clear one-word subject matches. Such evidence has an internal ranking floor of zero; this is not a calibrated model probability. Complete filenames are matched literally (case-insensitively), preventing similar asset names from being returned as exact matches.

Relevance verification precedes pagination, facets and download planning. Popularity cannot override the verified relevance ordering. Only deterministic query/content scores are cached (4096 pairs); visibility, licence state and filters are still checked on each request. Both models warm during startup. The search Dockerfile and requirements include the pinned Transformers dependency. Rebuild the search image for fresh deployments; the running local container has the dependency installed and the pinned model weights cached under `/models/huggingface`.

Hybrid search considers up to 200 keyword and 200 vector candidates by default. Use Exact Keyword for exhaustive lexical matching. Reranking improves precision but adds CPU latency to uncached queries. Model loading requires access to the official model repository once; inference does not send user queries or documents off-machine.

## Local verification, 23 September 2026

| Query | Before | After |
|---|---:|---:|
| dog | 46 | 2 (dog-care guide and retriever image) |
| dog in grass | 52 | 1 (retriever image) |
| red ball | 52 | 1 (retriever image) |
| quantum cryptography | 42 | 0 |
| zzxqvbnm | 43 | 0 |

`canine` finds the dog-care guide; `speech` returns seven speech recordings. Exact Keyword and Semantic modes both return the retriever for `red ball`. Result counts match facets; download-plan IDs match the displayed ranking for dog and red ball. The admin browser shows one result for the user's original `dog in grass` query and the new match label.

Measured uncached requests took roughly 3–4 seconds; a repeated dog query took 1–2 seconds on this local CPU setup. These are sample observations, not an accuracy benchmark or latency guarantee. Broader labelled relevance evaluation remains advisable as the catalog grows, especially for synonyms, multilingual input and inaccurate enrichment metadata.

69 focused backend tests and 29 frontend tests passed; frontend build succeeded. A pre-existing SQL-string assertion was corrected to compile literal bound values before checking the zero boundary.

Model reference: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2

## Follow-up: short queries and broader regressions

The previous verifier rejected `man`, `person`, `people`, and `show me a dog`. The fixes include:

- Unicode-preserving tokenization and identifier separators.
- Symmetric plural forms, including man/men, woman/women and child/children. Person/people also covers these explicit human terms; the reverse expansion is not applied.
- Request prefixes such as "show me" are removed before retrieval, preserving descriptive terms.
- A trailing `without`, `excluding`, `except` or `not` clause is checked against descriptive/source text before ranking. This is a limited explicit exclusion syntax, not a general Boolean language or proof that an object is absent from an image.
- Zero-weight branches are not called and contribute no results. Invalid fusion parameters are rejected.
- Browse queries use the complete filtered keyword listing regardless of requested mode.
- Exact Keyword ordering is preserved from the database, preventing prefix-dependent popularity adjustments from changing pagination or download ordering.
- Integration fixtures now query actual visible catalog titles instead of assuming every deployment contains an "acceptance" asset. The download test recognizes zero as an unlimited per-file size.

Verified on the local catalog:

| Query | Result |
|---|---|
| man / men | Conversation: Joy; Friends Playing Outdoor Basketball |
| show me a dog | Dog-care guide and retriever image |
| dog without a ball | Dog-care guide only |
| red ball / dog in grass | Retriever image only |
| quantum cryptography / zzxqvbnm / !!! | No matches |

All 102 search backend tests and 29 frontend tests pass. Live checks also exercised file-type, size and resolution filters, pagination, facet totals and download-plan ordering in text/hybrid/vector modes. Typical sequential live requests took approximately 2.4-3.3 seconds after startup; timing varies with model cache and concurrent activity.

Remaining limits: candidate retrieval is bounded; captions and descriptions can still be inaccurate; the English-oriented models do not guarantee multilingual semantic quality. Explicit exclusions rely on indexed text, and the verifier sees a bounded set of passages rather than every token. These checks cover known regressions, not every possible query or every file's visual ground truth.

## Multimodal index revision, 24 September 2026

### Root-cause checks

Qdrant was green; 85/85 published files had 512-dimensional cosine vectors. A manual nonidentical-vector cosine matched Qdrant within 1.5e-8. Re-embedding three documents from their original tags-first inputs reproduced stored vectors at approximately 1.0 cosine. The sampled failures were not a connection, cosine calculation or model drift error.

### New architecture

- Separate collection `multimodal_files_v2` (override `SEMANTIC_COLLECTION`), preserving the legacy collection.
- Named `text` vectors: all-MiniLM-L6-v2, 384 dimensions, pinned revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`; normalized masked mean pooling.
- Named `visual` vectors: actual source image pixels / eight evenly spaced video frames, CLIP ViT-B-32 OpenAI QuickGELU, 512 dimensions. Frame timestamps are retained.
- Both named vectors use cosine and MAX_SIM across document passages/frames. One query vector retrieves the strongest matching passage/frame rather than averaging unrelated scenes.
- Text is split into overlapping 220-token passages, capped at 64 evenly distributed passages per file. Generated tags do not dominate these embeddings. Query-matching passages are passed to the reranker.
- Keyword retrieval is preserved. Text and visual retrieval merge by ranks; hybrid combines this with keyword results. Weak visual candidates are filtered before fusion so merely appearing in both branches is not enough to gain rank.
- Independent text and visual similarity evidence can preserve matches rejected by the text-only cross-encoder. Thresholds are configurable and locally calibrated, not probabilities.
- SQL publication, entitlement and user filters remain authoritative; only those IDs are sent to the v2 query. Metadata hydration rechecks visibility.
- Future enrichment writes both indexes while the new collection exists. Publication projection synchronizes both payloads. Find Similar uses the new source image representation, or text when visual content is absent; for videos it currently uses the first sampled frame.
- Admin enrichment displays the new representation counts and missing-visual status. The old vector visualization is explicitly labelled Legacy CLIP.

### Deployment and rollback

Build with the configured search container (model cache is shared):

```powershell
docker exec smsprsm-rds-search-1 python /app/scripts/rebuild_semantic_index.py
```

After restoring database/source connectivity, retry only absent visual representations:

```powershell
docker exec smsprsm-rds-search-1 python /app/scripts/rebuild_semantic_index.py --retry-missing-visuals
```

Then restart Search to load the new code. Restart AI workers and the gateway when safe to load future-indexing and admin-inspection updates. `USE_MULTIMODAL_INDEX=false` in the search service environment selects the legacy retrieval path without deleting either index. Fresh deployments must provision/backfill v2 before starting Search with this flag enabled; startup validates its schema. All source access uses the existing ingestion boundary and checksum verification.

### Activation and verification, 24 September 2026

The restored connection allowed the backfill to finish. All 85 published files now have text representations; all 51 image/video files have visual representations, and 34 files are nonvisual. The collection contains 354 text passage vectors and 219 image/frame vectors. Every stored vector passed dimension, finite-value and unit-normalization checks. No visual files remain unavailable. Search, AI workers and the gateway were restarted to activate retrieval, future indexing and admin inspection. Search readiness passed with Postgres, Redis and the vector collection available.

119 backend/monitoring tests and 19 AI pipeline tests (plus eight subtests) passed. The previously completed frontend run passed 29 tests and the production build (an existing static/dynamic import warning remains). The offline catalog-snapshot evaluation passes 17/17 labelled cases. After the current public IP was allowed in the RDS security group, the complete uninterrupted live run passed all 34 relevance cases (17 vector and 17 hybrid). Pagination, download-plan ordering, file-type/size/resolution filters, and facet-total checks passed in keyword, vector and hybrid modes; exact-filename search and browse ordering parity also passed. Browser verification of both vector and hybrid search for `man` returned Conversation: Joy and Friends Playing Outdoor Basketball. The hybrid UI showed results in 3.43 seconds (server search 2175 ms). Median live API request duration was 2.75 seconds for vector and 1.93 seconds for hybrid; these are local sample timings, not a load benchmark. No source recovery or activation work remains pending.

The first live verifier reused a short-lived service token; it now obtains fresh authentication headers for each request and saves completed query checks incrementally. Subsequent failures were confirmed as RDS connection drops/timeouts, including a direct IPv4 TCP timeout to port 5432 after the user changed networks again. Connectivity was restored after the security group was updated with the public IPv4 used by the app, and the final live run completed without errors. They were not Qdrant cosine failures. Request dependencies no longer reprovision/probe Qdrant on every request; startup still validates the collection and the client timeout is configurable.

Reports are in ignored `.integration/semantic-index-report.json`, `.integration/semantic-evaluation.json` and `.integration/live-search-verification.json`. Run the snapshot evaluation with `docker exec -w /app/services/search/backend smsprsm-rds-search-1 python -m scripts.evaluate_semantic_index`; it uses `/tmp/semantic-index-report.json` generated by the rebuild. Run live checks with `docker exec smsprsm-rds-gateway-1 python /app/scripts/verify_live_search.py`; the report is written to `/tmp/live-search-verification.json` inside that container. The labelled checks are specific to this sample catalog and are a development check, not a held-out benchmark.

Broader visual evaluation and threshold calibration remain useful. Video sampling can miss brief actions; passage caps can miss text in very large documents; inaccurate descriptions remain a source of errors. None of these scores is a confidence percentage. The legacy collection remains intact for rollback.
