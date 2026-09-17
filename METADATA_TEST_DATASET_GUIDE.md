# Metadata Test Datasets

`scripts/generate_metadata_test_datasets.ps1` creates three independent,
multimodal correctness datasets:

1. `metadata-csv` — one `metadata.csv` manifest in each category folder.
2. `stock-csv` — one `metadata11.csv` manifest in each category folder.
3. `sidecars` — one asset directory containing `.id`, `.desc`, `.tags`, `.lab`,
   and `.cate` files for every asset.

Each dataset contains `images`, `videos`, `audio`, `documents`, `text`, and
`csv` subfolders. Assets cover JPEG, PNG, GIF, WebP, MP4, AVI, MOV, MP3, WAV,
PDF, DOCX, TXT, and CSV. The three variants use different generated content,
so their SHA-256 hashes do not merely duplicate another dataset variant.

## Generate and upload

The generator uses the existing correctness generator and therefore requires
Python with Pillow, ReportLab and python-docx, plus FFmpeg.

```powershell
$bucket = "your-test-bucket"
$rootPrefix = "demos/metadata-formats/run-001"
$datasetRoot = "C:\ingestion-test\metadata-formats-run-001"

Set-Location "C:\Users\hrbrv\.gemini\antigravity\scratch\data-ingestion"

.\scripts\generate_metadata_test_datasets.ps1 `
    -Bucket $bucket `
    -S3RootPrefix $rootPrefix `
    -OutputRoot $datasetRoot

aws s3 sync `
    $datasetRoot `
    "s3://$bucket/$rootPrefix/" `
    --only-show-errors
```

Do not change the upload prefix after generation: stock-manifest
`target_path` values contain the bucket and prefix supplied to the generator.

## Select one subtree

The connector supports one S3 prefix at a time. For example:

```powershell
$selectedPrefix = "$rootPrefix/metadata-csv/images/"
$scope = @{
    prefix = $selectedPrefix
    max_objects = 100
    page_size = 1000
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Patch `
    -Uri "http://localhost:8000/admin/connectors/$connectorId/s3-scope" `
    -Headers $headers `
    -ContentType "application/json" `
    -Body $scope

Invoke-RestMethod `
    -Method Post `
    -Uri "http://localhost:8000/admin/ingestion/trigger/$connectorId" `
    -Headers $headers
```

Other selectable examples:

```text
.../metadata-csv/csv/
.../metadata-csv/videos/
.../stock-csv/audio/
.../stock-csv/documents/
.../sidecars/images/
.../sidecars/text/
```

To ingest two non-contiguous categories such as `images` and `csv` without the
other folders, run the two prefixes sequentially or create two connectors with
the same credentials and different prefixes. A connector currently accepts one
prefix, not a list of prefixes.
