param(
    [Parameter(Mandatory = $true)]
    [string]$Bucket,

    [Parameter(Mandatory = $true)]
    [string]$S3RootPrefix,

    [string]$OutputRoot
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputRoot = "C:\ingestion-test\metadata-formats-$timestamp"
}

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$baseGenerator = Join-Path $scriptRoot "generate_correctness_dataset.ps1"
if (-not (Test-Path -LiteralPath $baseGenerator -PathType Leaf)) {
    throw "Base correctness generator not found: $baseGenerator"
}

$outputParent = Split-Path -Parent $OutputRoot
New-Item -ItemType Directory -Force -Path $outputParent | Out-Null
if (Test-Path -LiteralPath $OutputRoot) {
    if (Get-ChildItem -LiteralPath $OutputRoot -Force | Select-Object -First 1) {
        throw "Output directory already exists and is not empty: $OutputRoot"
    }
}
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$normalizedPrefix = $S3RootPrefix.Replace("\", "/").Trim("/")
if ([string]::IsNullOrWhiteSpace($normalizedPrefix)) {
    throw "S3RootPrefix must identify a dedicated test prefix; the bucket root is not allowed."
}

$formats = @(
    [PSCustomObject]@{ Category = "images"; Extension = "jpg";  Mime = "image/jpeg"; Title = "JPEG image" },
    [PSCustomObject]@{ Category = "images"; Extension = "png";  Mime = "image/png"; Title = "PNG image" },
    [PSCustomObject]@{ Category = "images"; Extension = "gif";  Mime = "image/gif"; Title = "GIF image" },
    [PSCustomObject]@{ Category = "images"; Extension = "webp"; Mime = "image/webp"; Title = "WebP image" },
    [PSCustomObject]@{ Category = "videos"; Extension = "mp4"; Mime = "video/mp4"; Title = "MP4 video" },
    [PSCustomObject]@{ Category = "videos"; Extension = "avi"; Mime = "video/x-msvideo"; Title = "AVI video" },
    [PSCustomObject]@{ Category = "videos"; Extension = "mov"; Mime = "video/quicktime"; Title = "MOV video" },
    [PSCustomObject]@{ Category = "audio"; Extension = "mp3"; Mime = "audio/mpeg"; Title = "MP3 audio" },
    [PSCustomObject]@{ Category = "audio"; Extension = "wav"; Mime = "audio/wav"; Title = "WAV audio" },
    [PSCustomObject]@{ Category = "documents"; Extension = "pdf"; Mime = "application/pdf"; Title = "PDF document" },
    [PSCustomObject]@{
        Category = "documents"
        Extension = "docx"
        Mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        Title = "DOCX document"
    },
    [PSCustomObject]@{ Category = "text"; Extension = "txt"; Mime = "text/plain"; Title = "Text document" },
    [PSCustomObject]@{ Category = "csv"; Extension = "csv"; Mime = "text/csv"; Title = "CSV dataset" }
)

$variants = @("metadata-csv", "stock-csv", "sidecars")
$temporaryRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("ingestion-metadata-" + [Guid]::NewGuid())
New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null

try {
    foreach ($variant in $variants) {
        $variantWork = Join-Path $temporaryRoot $variant
        $variantRunId = [Guid]::NewGuid()
        $null = & $baseGenerator -OutputRoot $variantWork -RunId $variantRunId

        $variantRoot = Join-Path $OutputRoot $variant
        foreach ($category in ($formats.Category | Select-Object -Unique)) {
            New-Item -ItemType Directory -Force -Path (Join-Path $variantRoot $category) | Out-Null
        }

        $metadataRowsByCategory = @{}
        $stockRowsByCategory = @{}

        foreach ($format in $formats) {
            $sourcePath = Join-Path $variantWork ("supported\sample." + $format.Extension)
            if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
                throw "Expected generated file is missing: $sourcePath"
            }

            $assetId = ($variant.ToUpperInvariant() + "-" + $format.Extension.ToUpperInvariant())
            $description = "Generated $($format.Title) for structured metadata ingestion testing"
            $tags = "generated|$($format.Category)|$($format.Extension)"
            $duration = if ($format.Category -in @("videos", "audio")) { "2.0" } else { "" }
            $pageCount = if ($format.Extension -in @("pdf", "docx")) { "1" } else { "" }

            if ($variant -eq "sidecars") {
                $assetFolder = Join-Path (Join-Path $variantRoot $format.Category) ("asset-" + $format.Extension)
                New-Item -ItemType Directory -Force -Path $assetFolder | Out-Null
                Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $assetFolder ("." + $format.Extension))
                Set-Content -LiteralPath (Join-Path $assetFolder ".id") -Value $assetId -Encoding utf8
                Set-Content -LiteralPath (Join-Path $assetFolder ".desc") -Value $description -Encoding utf8
                Set-Content -LiteralPath (Join-Path $assetFolder ".tags") -Value $tags.Replace("|", ",") -Encoding utf8
                Set-Content -LiteralPath (Join-Path $assetFolder ".lab") -Value "correctness,multimodal" -Encoding utf8
                Set-Content -LiteralPath (Join-Path $assetFolder ".cate") -Value $format.Category -Encoding utf8
                continue
            }

            $filename = "sample-$($format.Extension).$($format.Extension)"
            $destinationFolder = Join-Path $variantRoot $format.Category
            Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $destinationFolder $filename)

            if ($variant -eq "metadata-csv") {
                if (-not $metadataRowsByCategory.ContainsKey($format.Category)) {
                    $metadataRowsByCategory[$format.Category] = [System.Collections.Generic.List[object]]::new()
                }
                $metadataRowsByCategory[$format.Category].Add([PSCustomObject]@{
                    id = $assetId
                    filename = $filename
                    title = $format.Title
                    description = $description
                    category = $format.Category
                    tags = $tags
                    duration_seconds = $duration
                    page_count = $pageCount
                })
            }

            if ($variant -eq "stock-csv") {
                if (-not $stockRowsByCategory.ContainsKey($format.Category)) {
                    $stockRowsByCategory[$format.Category] = [System.Collections.Generic.List[object]]::new()
                }
                $objectKey = "$normalizedPrefix/stock-csv/$($format.Category)/$filename"
                $stockRowsByCategory[$format.Category].Add([PSCustomObject]@{
                    asset_id = $assetId
                    target_path = "s3://$Bucket/$objectKey"
                    title = $format.Title
                    brand = "Ingestion Test Vendor"
                    description = $description
                    keywords = "$($format.Category),$($format.Extension),generated"
                    categories = "$($format.Category),correctness"
                    contributor_id = "test-generator"
                    duration_seconds = $duration
                    page_count = $pageCount
                })
            }
        }

        foreach ($category in $metadataRowsByCategory.Keys) {
            $manifestPath = Join-Path (Join-Path $variantRoot $category) "metadata.csv"
            $metadataRowsByCategory[$category] | Export-Csv -LiteralPath $manifestPath -NoTypeInformation -Encoding utf8
        }
        foreach ($category in $stockRowsByCategory.Keys) {
            $manifestPath = Join-Path (Join-Path $variantRoot $category) "metadata11.csv"
            $stockRowsByCategory[$category] | Export-Csv -LiteralPath $manifestPath -NoTypeInformation -Encoding utf8
        }
    }
}
finally {
    $resolvedTemporaryRoot = [System.IO.Path]::GetFullPath($temporaryRoot)
    $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedTemporaryRoot.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedTemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$allFiles = Get-ChildItem -LiteralPath $OutputRoot -File -Recurse
$assetFiles = $allFiles | Where-Object {
    $_.Name -notin @("metadata.csv", "metadata11.csv", ".id", ".desc", ".tags", ".lab", ".cate")
}

[PSCustomObject]@{
    OutputRoot = $OutputRoot
    S3Destination = "s3://$Bucket/$normalizedPrefix/"
    DatasetCount = 3
    AssetCount = $assetFiles.Count
    TotalFileCount = $allFiles.Count
    TotalBytes = ($allFiles | Measure-Object Length -Sum).Sum
}
