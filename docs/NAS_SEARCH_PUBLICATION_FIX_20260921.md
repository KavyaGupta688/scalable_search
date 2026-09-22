# NAS search publication correction — 21 September 2026

## Cause

The NAS dog image `01a0c2c8-0ea7-7ca3-a2d9-5526ec886b54` had tags, a caption and a vector, but its task was `needs_review` and its Search projection was unpublished. The recorded NSFW score was 0.5004537105560303. Search correctly enforced the existing publication policy; lowering search restrictions would have bypassed review.

The AI adapter incorrectly took the highest score of **every** NudeNet object detection. NudeNet detects faces, feet, covered body parts and other non-explicit classes as well as explicit nudity. Object detection confidence is not an overall NSFW score. This bug withheld the dog, the vegetable-pizza image and four conversation videos in this NAS dataset.

## Correction

- Explicit-nudity scoring now considers exposed buttocks, female breasts, genitalia and anus. Faces, feet, bellies, armpits, male chest and covered body classes do not independently trigger explicit-content review.
- Unrecognized classes, invalid scores and failures on any sampled image/frame prevent safety clearance. Real explicit flags, incomplete checks, toxicity, entitlement expiry and other review rules remain enforced.
- The NudeNet adapter version is now `nudenet-v3-explicit-classes-v1`. This changes the composite model version, preserving earlier metadata when the standard retry pipeline persists new results.
- All six unpublished affected NAS records were retried through the authenticated API. No direct database publication override or threshold reduction was used.
- Enrichment now explains unpublished state and possible safety false positives. The inspector selector also fits the available width.

## Verification

Nine class-policy tests passed. The existing AI correctness suite passed 17 tests and eight subtests before two additional adapter regressions were added; a focused rerun passed the two new cases and the existing explicit-content review case (three tests, two subtests). Frontend build and all 17 frontend tests passed.

Live source reprocessing completed and published the dog and pizza images. Real Search API calls found the dog in text, hybrid and vector modes. A browser check confirmed the image appears in the administrator's Exact Keyword results for `dog`.

Image-tag checks scoped to NAS connector `0f91a09b-127a-4a9c-b61a-f844f1479f3f` returned: dog 1, flower 1, car 2, beach 1, pizza 1, city 1, red 3, water 2, outdoor 5, search_dog_001 1. The second car match is the city/taxi image: Search combines vendor and generated tags, so combined tag counts need not equal a vendor-only manifest specification.

All four conversation videos subsequently completed and published, with the final retry completing at 08:38:53 UTC. All six affected files recovered through normal processing with no persisted task errors. The old dog/pizza metadata was verified alongside the corrected versions; their explicit-nudity scores changed to zero, while their independent AI-origin assessments remained unchanged. The final live Search check also found all four conversation videos. Across all finalized tasks, the audit found no missing Search projection or completed/partial task unexpectedly left unpublished.

The fully loaded dog preview, metadata and publication indicator were verified in the Enrichment inspector at desktop and mobile sizes without horizontal overflow or JavaScript errors. No claim of universally accurate safety or AI-origin classification is made. Both remain model estimates; this change fixes an adapter bug rather than certifying the detector.

## Reproduction

- `tests/test_nsfw_class_policy.py`: isolated class-policy regression tests.
- `modules/ai_tag_description_generation/tests/test_pipeline_correctness.py`: adapter and pipeline review regressions.
- `tests/integration/nas-search-publication.cjs`: authenticated live search modes, image-tag checks and browser result.
- `tests/integration/retry-nas-safety.cjs`: explicit, dataset-specific mutation helper; only run when intentionally reprocessing these six records. It reads ignored local credentials without logging them.
- Screenshot: ignored `.integration/nas-dog-search-fixed.png`.

Changes remain local on `Feature/Integration`.
