# Real public S3 dataset acceptance — 21 September 2026

Work is local on `Feature/Integration`, starting at `990d150`. **Final bounded acceptance passed:** seven real source objects ingested, completed AI enrichment and published; both dataset API runs passed all 11 check groups, and eight live browser groups passed. Earlier memory failures, a DNS interruption and model-quality limits are documented below. This report supplements the earlier generated benchmark; it does not replace that benchmark's historical results or certify general production stability.

## Source and scope

Amazon Berkeley Objects (ABO), a real product catalog with photographs, multilingual listings and 3D assets:

- [Official dataset registry](https://registry.opendata.aws/amazon-berkeley-objects/)
- [Dataset README and attribution](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/README.md)
- [Supplied license](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/LICENSE-CC-BY-4.0.txt)

The public bucket is `amazon-berkeley-objects`, region `us-east-1`. This bounded test reads six original photographs under `images/original/00/` and `static_html/ABO_CVPR2022.pdf`. It does not ingest the complete catalog, its 3D assets, or arbitrary archives. No source objects were uploaded, changed or deleted. No model outputs were substituted.

Attribution: data © Amazon.com. Dataset construction: Matthieu Guillaumin, Thomas Dideriksen, Kenan Deng, Himanshu Arora, Jasmine Collins and Jitendra Malik. The bucket's README/license state CC BY 4.0; the registry lists CC BY-NC 4.0. This discrepancy is recorded rather than resolved by assumption. These copies are for local development testing. Original source bytes remain unchanged; downloaded test packages receive the application's forensic metadata watermark. This report does not claim endorsement or commercial licensing clearance.

| Source | Connector | Initial run | Ingestion |
| --- | --- | --- | --- |
| Six photographs | `6aac39f7-2078-41e6-89ae-0c2b4b564c51` | `15711e6c-e99b-4fb0-9fc5-249363368e54` | 6/6 succeeded; 3,222,641 bytes |
| Research paper | `cee93f03-741e-497d-b4f6-626987165815` | `b9ad1d85-3242-4639-ae85-3b1a0b1f6a6c` | 1/1 succeeded; 20,525,649 bytes |

Image basenames: `00000529.jpg`, `00003a93.jpg`, `000088e1.jpg`, `0000b301.jpg`, `0000b9b8.jpg`, `0000bd76.jpg`. The normal application sources, RDS credentials and database volumes were preserved. Only the approved `smsprsm_integration` database was migrated; shared `samsungdb` was not touched.

## Repairs exposed by real data

1. Added explicitly unsigned public S3 access. Existing static-key and AssumeRole configurations remain supported. Anonymous requests cannot include supplied credentials or a role.
2. Added connector metadata policies: required manifests, optional manifests, or files only. Migration ingestion `015` preserves `required` for existing connectors. A file without a custom CSV can now reach AI without invented vendor descriptions/tags.
3. Fixed absent vendor metadata crossing the ingestion/AI event boundary. Earlier ingestion emitted `null` while AI required an object. New events emit `{}`; the consumer also accepts old explicit absence. Supplied malformed metadata remains invalid. The seven rejected test events were replayed through the outbox; their initial DLQ history was retained.
4. The first image exhausted the 4 GiB AI consumer limit during RAM++ loading. Changed the loader to memory-map the existing checkpoint and assign its tensors, preserving interpolation/key mapping and FP32 weights. Standalone actual loading peaked at 1,838.7 MiB RSS. The confirmed dead worker was stopped, its one orphan lease released with an Audit record, and the same document resumed. No successful output or source record was replaced.
5. Reduced search database round trips: all facets in one aggregate query, keyword count combined with the page query, one session validation per browser request, and no redundant post-commit Audit-event refresh. Revocation is still checked on each request; Audit is still durable.
6. Added a bounded query-embedding cache (256 entries, independent returned lists) and offloaded synchronous Qdrant calls from the request event loop. Results, users and entitlements are not cached.
7. Search initializes CLIP before accepting requests. Semantic/hybrid facets now use the eligible catalog instead of excluding semantic matches with exact-keyword predicates.
8. Long-document chunking now stops after the final full/partial chunk instead of emitting an overlap-only tail on boundary lengths; six text-coverage/boundary tests passed.
9. The PDF hit a separate BART loading memory limit. Standard BART loading peaked at 3,490 MiB before inference. Added pinned Accelerate 0.20.3 and low-memory BART loading, repairing the installed Transformers 4.28 shared encoder/decoder embedding aliases, including the original BART-CNN decoder-only checkpoint layout. Actual FP32 BART classification then succeeded at 1,800 MiB peak RSS; the real BART-CNN checkpoint also produced a summary in a separate smoke check. Classification and summarization loaders pass tensor/alias/inference-equivalence tests on small saved safetensors and legacy `.bin` checkpoints. The PDF's orphan lease was released only after the failed worker was stopped. Its initial acceptance timeout is retained locally.
10. Full-length BART inference still exceeded the 4 GiB worker limit after loading was repaired. The low-memory Compose profile now limits classification/summary input to 512 opening tokens, clamped to model/tokenizer limits; the normal default remains 1024. Full extracted text is preserved. This is a resource/coverage tradeoff, not whole-document hierarchical summarization or a claim of unchanged long-input model predictions. No precision or checkpoint changes were made.
11. Container DNS briefly failed to resolve RDS during the first image build, interrupting the resumed PDF acceptance runner. Resolution recovered without changing RDS or switching databases. The final image was rebuilt with all loader fixes and the three AI services recreated while preserving model/database volumes.

## Measured search latency

Same gateway, RDS and 43 published documents; three requests per mode (`chair`, `book`, `chair`), limit 10. Measurements are full HTTP wall times including authentication and durable audit. Text queries had zero matches; hybrid/vector queries had 43 candidates. The final run occurred with background AI work, so this small sample is not a load-test SLA.

| Mode | Before median | Final median | Reduction |
| --- | ---: | ---: | ---: |
| Text | 6,757.5 ms | 2,116.4 ms | 69% |
| Hybrid | 3,856.8 ms | 2,822.0 ms | 27% |
| Vector | 4,170.3 ms | 2,420.4 ms | 42% |

An intermediate run showed 2,049 / 2,103 / 2,294 ms medians, but its first hybrid request took 11.5 seconds loading CLIP. Startup initialization removed that request-time cold load: the final first hybrid request was 2,467 ms. Remaining latency includes cloud database round trips. Larger catalogs, concurrent users and production network placement are not certified.

A later natural-language check on the new photo dataset mostly took about 0.7–0.9 seconds after its opening requests, but one first text request still took 11.95 seconds and one hybrid request 3.5 seconds. Those tail delays remain a limitation; the small median comparison does not prove every search is fast.

## Validation evidence

- Frontend: 16 adapter/contract tests passed and the production build passed. Vite reports an existing mixed static/dynamic import warning. No configured frontend lint/type-check suite is claimed.
- Ingestion: the final full suite passed 50 tests, including anonymous credential rejection, metadata-policy precedence, files-only treatment of genuine files named `metadata.csv`, and empty-metadata event consistency.
- Gateway/shared authentication: 39 tests passed, followed by all 30 gateway tests after adding once-per-request validation/revocation coverage. The live two-instance RDS account/session/revocation check passed and removed its temporary records.
- Search: the final full suite passed all 16 tests. Earlier failures exposed a fixture that assumed the catalog contained “acceptance” (now queries an actual filename) and the semantic-facet bug fixed above. Aggregate/count/cache regressions are included.
- AI event contract: five tests passed. Nine BART loading/tokenizer-bound, document-boundary and RAM loader tests passed, then all four BART cases passed after adding the legacy decoder-only checkpoint regression (11 distinct tests overall). Actual RAM weights, a short-input BART classifier and the real BART-CNN summarizer also ran successfully.
- Live Edge browser: eight final check groups passed using real services: administrator screens, public S3 form, registration and all search modes, protected image preview/similarity, actual ZIP delivery/history, real PDF extracted-text preview, standard-user route restrictions, and mobile layout. No uncaught browser errors. Initial browser check exposed and fixed the metadata selector's accessible label. Final screenshots were visually inspected at 1440-pixel desktop width; the browser also checked a 390-pixel mobile viewport.

Both final API runs passed all 11 check groups: both-role discovery; filtered pagination/facets; original-byte SHA256/size for every file; details and similarity; complete archives; another user's ownership rejection; unchanged rescan; revoked-session rejection; and persistent Audit. JPEG forensic verification passed; the PDF archive passed ZIP integrity and delivery checks, with no claim of native PDF forensic verification. All seven assets reached `completed` and were published. Rescans skipped six photos and one PDF without processing bytes or creating new canonical documents. The ingestion outbox had zero pending deliveries. All four module readiness endpoints returned HTTP 200; the final AI image was built and applied to API, consumer and Celery worker.

The final 21 natural-language searches used the real assets and both source filters. For seven manually selected queries, the expected object ranked first in 6/7 text, 5/7 hybrid and 6/7 vector queries. The wrench query had no exact keyword hit and ranked sixth in both semantic modes; the suitcase ranked second in hybrid. All other expected files ranked first. Final request times ranged from 698 to 1,568 ms, including authentication and Audit. The PDF filter has only one file, so its first-place rank establishes retrieval, not ranking quality. This tiny, manually inspected sample is not an unbiased relevance benchmark.

Manual image inspection identified real quality limitations: `00000529.jpg` shows a wheeled case underside, but its caption calls the wheels handles and appends noisy OCR. `0000b9b8.jpg` correctly has a `wrench` tag, but BLIP's description is garbled (“a set of wrens and wren wrens on white background”). Other descriptions identify the photo frame, laundry bag, bench/rug and phone case. Tags include correct objects alongside background details and OCR noise. These observations are not a labelled precision/recall evaluation; no captions or confidence values were manually repaired to make the test pass.

The paper exposes another quality limit: its native PDF text contains joined words, line-break hyphenation and dense reference/table entities. Those artifacts carry into its BART summary and tags. Better PDF layout extraction, tag filtering and a labelled retrieval/description evaluation remain follow-up work. Successful processing is not proof that every tag or sentence is accurate. The earlier 43 synthetic/test records remain preserved; select an ABO dataset to isolate these real sources in Search.

## Reproduction and evidence

After provisioning the normal RDS stack and running ingestion migration `015`, run `tests/integration/public_dataset_setup.py` inside the gateway. It connects two bounded public sources through the actual API and prints their connector/run IDs. Then run `tests/integration/dataset_acceptance.py <connector> <run> --query '*' --page-size 2` in the AI container for each source. The small page size exercises real pagination even on six images. Run `tests/integration/public_dataset_relevance.py <photo-connector> <paper-connector>` inside gateway and `tests/integration/public-dataset-browser.cjs <photo-connector> <paper-connector>` with Playwright/Edge on the host.

Local, ignored evidence: `.integration/abo-setup.json`, `search-before.json`, `search-after.json`, `search-final.json`, `abo-relevance-initial.json`, `abo-relevance.json`, `abo-images-acceptance.json`, `abo-paper-acceptance.json`, `abo-paper-initial-timeout.json`, `abo-images/`, `public-dataset-browser/`. Detailed API reports are also in `/models/provisioning/dataset-<connector>-results.json`. These contain no source credentials. Dataset files/model checkpoints are not committed.

## Meaning of “any S3 bucket”

The source is configurable, not hardcoded to `demo-bucket-prism`: bucket, region/endpoint, prefix, bounds, addressing/signature mode and authentication are configurable. Private sources require valid list/read permissions, role trust and any required decryption permissions. Public sources require public listing/read access. Unsupported formats, archive/3D expansion, Requester Pays, expired entitlements, unavailable objects and unsupported storage retrieval classes do not become successful ingestion merely because an endpoint speaks S3. Cross-account AssumeRole and third-party S3 providers need representative live acceptance environments; NAS remains deferred. The new natural-media run covers images and a PDF, not fresh audio/video accuracy or scale testing.
