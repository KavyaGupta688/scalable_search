param(
    [Parameter(Mandatory = $true)]
    [Guid]$RunId,

    [string]$ApiBaseUrl = "http://localhost:8000",
    [string]$AccessToken
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($AccessToken)) {
    $secure = Read-Host "Paste the API access token" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $AccessToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

$tokenMatch = [regex]::Match(
    $AccessToken,
    '(?<![A-Za-z0-9_-])([A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)(?![A-Za-z0-9_-])'
)
if (-not $tokenMatch.Success) {
    throw "No valid JWT was found."
}

$headers = @{ Authorization = "Bearer $($tokenMatch.Groups[1].Value)" }
$run = Invoke-RestMethod `
    -Method Get `
    -Uri "$ApiBaseUrl/admin/ingestion/runs/$RunId" `
    -Headers $headers

$outputPath = Join-Path (Get-Location) "ingestion-run-$RunId.json"
$run | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outputPath -Encoding UTF8
$run | Format-List
Write-Host "Run report saved to $outputPath"

$AccessToken = $null
$headers = $null
