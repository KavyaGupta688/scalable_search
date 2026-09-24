[CmdletBinding()]
param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..\.integration'))

$ErrorActionPreference = 'Stop'
$targetDirectory = [IO.Path]::GetFullPath($OutputDirectory)
$names = @('stack.env', 'rds-runtime.env', 'monitoring.env')
foreach ($name in $names) {
    if (Test-Path -LiteralPath (Join-Path $targetDirectory $name)) {
        throw "Refusing to overwrite existing $name. Use a new directory to generate a reference copy."
    }
}
function New-PrivateKey {
    $bytes = New-Object byte[] 48
    $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return ([BitConverter]::ToString($bytes)).Replace('-', '').ToLowerInvariant()
}
$stack = @(
    '# Generated locally. Keep this file private and out of Git.'
    '# Replace every REPLACE_ value before starting. See docs/TEAMMATE_SETUP.md.'
    "POSTGRES_PASSWORD=$(New-PrivateKey)"
    "INTERNAL_JWT_SECRET=$(New-PrivateKey)"
    'NEXUS_JWT_SECRET=REPLACE_WITH_TEAM_SHARED_LOGIN_SIGNING_KEY'
    'AUTH_DATABASE_URL_SYNC=postgresql+psycopg2://REPLACE_USER:REPLACE_URL_ENCODED_PASSWORD@REPLACE_RDS_HOST:5432/smsprsm_integration?sslmode=require'
    "WATERMARK_SECRET_KEY=$(New-PrivateKey)"
    "CODEC_WATERMARK_SECRET=$(New-PrivateKey)"
    "VAULT_TOKEN=$(New-PrivateKey)"
    'BOOTSTRAP_ADMIN_EMAIL=admin@platform.internal'
    "BOOTSTRAP_ADMIN_PASSWORD=$(New-PrivateKey)"
    'INGESTION_MAX_POLL_INTERVAL_MS=7200000'
    'JPEG_CODEC_WATERMARK=false'
    'LOSSLESS_SIGNAL_WATERMARK=false'
    'NATIVE_AUDIO_WATERMARK=false'
    'NATIVE_VIDEO_WATERMARK=false'
)
$rds = @(
    '# Dedicated module database on RDS, allocated by infrastructure.'
    '# Do not point independent workers at the shared module DB by accident.'
    'RDS_DATABASE_URL=postgresql+asyncpg://REPLACE_USER:REPLACE_URL_ENCODED_PASSWORD@REPLACE_RDS_HOST:5432/REPLACE_DEDICATED_MODULE_DATABASE?ssl=require'
    'RDS_DATABASE_URL_SYNC=postgresql+psycopg2://REPLACE_USER:REPLACE_URL_ENCODED_PASSWORD@REPLACE_RDS_HOST:5432/REPLACE_DEDICATED_MODULE_DATABASE?sslmode=require'
)
$monitoring = @('GRAFANA_ADMIN_USER=admin', "GRAFANA_ADMIN_PASSWORD=$(New-PrivateKey)")
New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllLines((Join-Path $targetDirectory 'stack.env'), [string[]]$stack, $utf8)
[IO.File]::WriteAllLines((Join-Path $targetDirectory 'rds-runtime.env'), [string[]]$rds, $utf8)
[IO.File]::WriteAllLines((Join-Path $targetDirectory 'monitoring.env'), [string[]]$monitoring, $utf8)
Write-Output "Created three private environment templates in $targetDirectory. No services or databases were changed."
Write-Output 'Replace all REPLACE_ placeholders using the setup guide before starting Docker.'
