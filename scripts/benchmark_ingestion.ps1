param(
    [Parameter(Mandatory = $true)]
    [Guid]$ConnectorId,

    [Parameter(Mandatory = $true)]
    [ValidateRange(1, [long]::MaxValue)]
    [long]$ExpectedObjects,

    [ValidateSet("S3", "NAS_SMB", "NAS_NFS")]
    [string]$SourceType = "S3",

    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$PrometheusBaseUrl = "http://localhost:9090",
    [ValidateRange(2, 300)]
    [int]$PollSeconds = 10,

    # Prefer passing a PowerShell variable (`-AccessToken $accessToken`) so
    # the JWT never has to be copied or printed. If omitted, prompt securely.
    [string]$AccessToken
)

$ErrorActionPreference = "Stop"

function Read-SecretText([string]$Prompt) {
    $secure = Read-Host $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Get-PrometheusValue([string]$Query) {
    $uri = "$PrometheusBaseUrl/api/v1/query?query=$([Uri]::EscapeDataString($Query))"
    $response = Invoke-RestMethod -Method Get -Uri $uri
    if ($response.status -ne "success" -or $response.data.result.Count -eq 0) {
        return 0.0
    }
    return [double]$response.data.result[0].value[1]
}

function Get-Snapshot {
    return [ordered]@{
        # The orchestration-level counter is emitted for S3 and both NAS
        # implementations; the S3 page counter is intentionally S3-only.
        enumerated = Get-PrometheusValue "sum(ingestion_files_processed_total{source_type=`"$SourceType`",outcome=`"enumerated`"}) or vector(0)"
        processed  = Get-PrometheusValue "sum(ingestion_files_processed_total{source_type=`"$SourceType`",outcome!=`"enumerated`"}) or vector(0)"
        failed     = Get-PrometheusValue "sum(ingestion_files_failed_total{source_type=`"$SourceType`"}) or vector(0)"
        bytes      = Get-PrometheusValue "sum(ingestion_throughput_bytes_total{source_type=`"$SourceType`"}) or vector(0)"
        success    = Get-PrometheusValue "sum(ingestion_files_processed_total{source_type=`"$SourceType`",outcome=`"success`"}) or vector(0)"
        duplicate  = Get-PrometheusValue "sum(ingestion_files_processed_total{source_type=`"$SourceType`",outcome=`"duplicate`"}) or vector(0)"
        skipped    = Get-PrometheusValue "sum(ingestion_files_processed_total{source_type=`"$SourceType`",outcome=`"skipped`"}) or vector(0)"
    }
}

function Get-StageSnapshot {
    $result = [ordered]@{}
    foreach ($stage in $stages) {
        $sumQuery = "sum(ingestion_processing_duration_seconds_sum{source_type=`"$SourceType`",stage=`"$stage`"}) or vector(0)"
        $countQuery = "sum(ingestion_processing_duration_seconds_count{source_type=`"$SourceType`",stage=`"$stage`"}) or vector(0)"
        $result[$stage] = [ordered]@{
            cumulative_seconds = Get-PrometheusValue $sumQuery
            sample_count = Get-PrometheusValue $countQuery
        }
    }
    return $result
}

$stages = @(
    "enumeration_total", "queue_wait", "source_read", "hashing", "validation", "minio_exists",
    "minio_write", "metadata", "postgresql_read", "postgresql_write",
    "postgresql_commit", "total"
)

$tokenInput = if ([string]::IsNullOrWhiteSpace($AccessToken)) {
    Read-SecretText "Paste the API access token"
} else {
    $AccessToken
}
# Accept either the raw JWT, a copied "Bearer <JWT>" header, or the JSON
# returned by /auth/token. Extracting the token also removes invisible
# whitespace/control characters that PowerShell refuses in HTTP headers.
$tokenMatch = [regex]::Match(
    $tokenInput,
    '(?<![A-Za-z0-9_-])([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)(?![A-Za-z0-9_-])'
)
if (-not $tokenMatch.Success) {
    throw "No valid JWT was found. Paste the access_token value returned by POST /auth/token."
}
$token = $tokenMatch.Groups[1].Value
$tokenInput = $null
$headers = @{ Authorization = "Bearer $token" }
$before = Get-Snapshot
$stagesBefore = Get-StageSnapshot
$startedAt = Get-Date

$trigger = Invoke-RestMethod `
    -Method Post `
    -Uri "$ApiBaseUrl/admin/ingestion/trigger/$ConnectorId" `
    -Headers $headers

$runId = $trigger.run_id
Write-Host "Run ID: $runId"
Write-Host "Do not start another $SourceType run while this benchmark is active."

do {
    Start-Sleep -Seconds $PollSeconds
    $now = Get-Snapshot
    $enumerated = [long]($now.enumerated - $before.enumerated)
    $processed = [long]($now.processed - $before.processed)
    $failed = [long]($now.failed - $before.failed)
    $terminal = $processed + $failed
    $elapsed = ((Get-Date) - $startedAt).TotalSeconds
    $mibPerSecond = if ($elapsed -gt 0) {
        (($now.bytes - $before.bytes) / 1MB) / $elapsed
    } else { 0 }
    Write-Host ("enumerated={0} terminal={1}/{2} failed={3} elapsed={4:N1}s throughput={5:N2} MiB/s" -f `
        $enumerated, $terminal, $ExpectedObjects, $failed, $elapsed, $mibPerSecond)
} while ($terminal -lt $ExpectedObjects)

$finishedAt = Get-Date
$after = Get-Snapshot
$elapsedSeconds = ($finishedAt - $startedAt).TotalSeconds
$bytesProcessed = [long]($after.bytes - $before.bytes)

$stagesAfter = Get-StageSnapshot
$stageResults = [ordered]@{}
foreach ($stage in $stages) {
    $count = $stagesAfter[$stage].sample_count - $stagesBefore[$stage].sample_count
    $seconds = $stagesAfter[$stage].cumulative_seconds - $stagesBefore[$stage].cumulative_seconds
    $stageResults[$stage] = [ordered]@{
        cumulative_seconds = [math]::Round($seconds, 3)
        sample_count = [long]$count
        mean_seconds = if ($count -gt 0) { [math]::Round($seconds / $count, 6) } else { $null }
    }
}

$report = [ordered]@{
    run_id = $runId
    connector_id = $ConnectorId.ToString()
    source_type = $SourceType
    expected_objects = $ExpectedObjects
    started_at = $startedAt.ToUniversalTime().ToString("o")
    finished_at = $finishedAt.ToUniversalTime().ToString("o")
    elapsed_seconds = [math]::Round($elapsedSeconds, 3)
    terminal_outcomes = [long](($after.processed + $after.failed) - ($before.processed + $before.failed))
    enumerated = [long]($after.enumerated - $before.enumerated)
    succeeded = [long]($after.success - $before.success)
    duplicates = [long]($after.duplicate - $before.duplicate)
    skipped = [long]($after.skipped - $before.skipped)
    failed = [long]($after.failed - $before.failed)
    peak_enumerator_memory_bytes = [long](Get-PrometheusValue 'max(ingestion_process_memory_peak_bytes) or vector(0)')
    bytes_processed = $bytesProcessed
    mib_per_second = if ($elapsedSeconds -gt 0) { [math]::Round((($bytesProcessed / 1MB) / $elapsedSeconds), 3) } else { 0 }
    objects_per_second = if ($elapsedSeconds -gt 0) { [math]::Round(($ExpectedObjects / $elapsedSeconds), 3) } else { 0 }
    projected_one_tib_hours = if ($bytesProcessed -gt 0) {
        [math]::Round(((1TB / $bytesProcessed) * $elapsedSeconds) / 3600, 2)
    } else { $null }
    stage_cumulative_totals = $stageResults
}

$outputPath = Join-Path (Get-Location) "benchmark-$runId.json"
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outputPath -Encoding UTF8
$report | Format-List
Write-Host "Report saved to $outputPath"

$token = $null
$headers = $null
