# Structured Vendor Metadata Journey

The ingestion service does not extract descriptive metadata from the binary and
does not run Apache Tika. The vendor-provided metadata is authoritative.

## Supported layouts

### `metadata.csv`

One header row and one row per asset. A row is matched by exact,
case-insensitive `filename` in the manifest directory. `filename` is used only
for matching. Common descriptive fields are normalized into clear columns;
explicitly unwanted image/counter fields are discarded.

### Stock-library CSV (`metadata11.csv` by default)

A row is matched by normalized `target_path`, including full `s3://` URIs.
`target_path` is used only for matching. `asset_id` becomes
`external_asset_id`; keywords merge into tags. Unknown vendor fields such as
video duration are retained in bounded `additional_metadata` JSONB.

### Per-asset sidecars

The asset directory can contain `.id`, `.desc`, `.tags`, `.lab`, and `.cate`.
All files are plain UTF-8. `.tags` and `.lab` are merged and de-duplicated.
Missing individual sidecars are allowed. By default, sidecar requests are
skipped after a manifest row matches, avoiding five remote lookups per asset.
Set `METADATA_SIDECARS_WITH_MANIFEST=true` only when sidecars intentionally
augment a manifest; their non-empty values then take precedence.

The worker checks the asset directory followed by its ancestors, so a manifest
can be placed in a file-type subfolder or at the configured prefix root.
Manifest and sidecar filenames are configurable with `METADATA_MANIFEST_NAMES`
and `METADATA_SIDECAR_NAMES`.

## Processing flow

1. Enumeration identifies metadata control files and does not publish them as
   document jobs.
2. The worker resolves and validates the small metadata files before reading the
   asset binary. `METADATA_MAX_FILE_BYTES` prevents unbounded memory use.
3. With `METADATA_REQUIRED=true`, no matching metadata is a permanent job error.
   Set it to `false` only for legacy backfills where an empty metadata row is
   acceptable.
4. The asset binary is streamed once for MIME validation and SHA-256. It is not
   copied, spooled, or sent to Tika.
5. `documents` stores canonical identity; `source_assets` stores physical source
   locations; `document_metadata` stores one typed row per physical source and
   links it to both `source_asset_id` and `document_id`.
6. The downstream Kafka event contains the same structured metadata and direct
   source locator, never connector credentials.

For unchanged assets, a new run refreshes the structured metadata without
re-reading the full binary. Exact duplicate bytes at another location link to
the existing document but keep their own title/tags/provenance row.

## Queries

```sql
SELECT d.id, d.mime_type, d.checksum_sha256,
       m.external_asset_id, m.title, m.primary_category,
       m.tags, m.additional_metadata
FROM documents AS d
LEFT JOIN document_metadata AS m ON m.document_id = d.id
ORDER BY d.id DESC;

SELECT m.brand, m.contributor_id, m.additional_metadata
FROM document_metadata AS m
WHERE m.document_id = :document_id;

SELECT d.id, count(sa.id) AS physical_locations
FROM documents AS d
JOIN source_assets AS sa ON sa.document_id = d.id
GROUP BY d.id
HAVING count(sa.id) > 1;
```

Migration `010` creates the initial table. Migration `011` prunes image-only and
duplicated fields, merges keywords into tags, and adds bounded
`additional_metadata`. Existing documents are backfilled by safely re-running
their connector scope; unchanged fingerprints avoid another binary read.
