param(
    [string]$OutputRoot,
    [Guid]$RunId = [Guid]::NewGuid()
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python first."
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "ffmpeg was not found. Install it with: winget install --id Gyan.FFmpeg -e"
}

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputRoot = "C:\ingestion-test\correctness-demo-$timestamp"
}

$resolvedParent = Split-Path -Parent $OutputRoot
New-Item -ItemType Directory -Force $resolvedParent | Out-Null
if (Test-Path -LiteralPath $OutputRoot) {
    if (Get-ChildItem -LiteralPath $OutputRoot -Force | Select-Object -First 1) {
        throw "Output directory already exists and is not empty: $OutputRoot"
    }
}

$env:INGESTION_DEMO_ROOT = $OutputRoot
$env:INGESTION_DEMO_RUN_ID = $RunId.ToString()

$pythonCode = @'
from pathlib import Path
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas
from docx import Document
import csv
import json
import math
import os
import shutil
import struct
import wave
import zipfile

root = Path(os.environ["INGESTION_DEMO_ROOT"])
run_id = os.environ["INGESTION_DEMO_RUN_ID"]
supported = root / "supported"
unsupported = root / "unsupported"
duplicates = supported / "duplicates"
supported.mkdir(parents=True, exist_ok=True)
unsupported.mkdir(parents=True, exist_ok=True)
duplicates.mkdir(parents=True, exist_ok=True)

# Encode the run ID into pixels so every generated image has new content.
seed = int(run_id.replace("-", "")[:6], 16)
background = ((seed >> 16) & 255, (seed >> 8) & 255, seed & 255)
image = Image.new("RGB", (640, 480), background)
draw = ImageDraw.Draw(image)
draw.rectangle((30, 30, 610, 450), outline=(255, 255, 255), width=5)
draw.text((55, 205), "Data ingestion correctness demo", fill=(255, 255, 255))
draw.text((55, 235), f"Run: {run_id}", fill=(255, 255, 255))
image.save(supported / "sample.jpg", "JPEG", quality=90)
image.save(supported / "sample.png", "PNG")
image.save(supported / "sample.gif", "GIF")
image.save(supported / "sample.webp", "WEBP", quality=85)

# Exactly one intentional duplicate within this new dataset.
shutil.copyfile(supported / "sample.jpg", duplicates / "sample-copy.jpeg")

pdf = canvas.Canvas(str(supported / "sample.pdf"))
pdf.setTitle(f"Ingestion Demo PDF {run_id}")
pdf.setAuthor("Ingestion Demo")
pdf.drawString(72, 750, "PDF file for the ingestion correctness demo.")
pdf.drawString(72, 725, f"Unique run: {run_id}")
pdf.save()

doc = Document()
doc.core_properties.title = f"Ingestion Demo DOCX {run_id}"
doc.core_properties.author = "Ingestion Demo"
doc.add_heading("Data ingestion correctness demo", level=1)
doc.add_paragraph(f"Unique run: {run_id}")
doc.save(supported / "sample.docx")

(supported / "sample.txt").write_text(
    f"Plain-text ingestion demo.\nUnique run: {run_id}\n", encoding="utf-8"
)
with (supported / "sample.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(["id", "category", "run_id"])
    writer.writerow([1, "image", run_id])
    writer.writerow([2, "document", run_id])

# The UUID selects a different tone for every run; derived MP3 is unique too.
sample_rate = 44100
duration_seconds = 2
frequency = 220 + (int(run_id.replace("-", "")[:4], 16) % 500)
audio_signature = bytes.fromhex(run_id.replace("-", ""))
with wave.open(str(supported / "sample.wav"), "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(sample_rate)
    frames = bytearray()
    for index in range(sample_rate * duration_seconds):
        value = int(16000 * math.sin(2 * math.pi * frequency * index / sample_rate))
        # Embed all 128 UUID bits in valid PCM samples, guaranteeing that a
        # subsequent run does not reproduce the previous WAV hash.
        if index < len(audio_signature):
            value = (audio_signature[index] - 128) * 128
        frames.extend(struct.pack("<h", value))
    wav.writeframes(bytes(frames))

(unsupported / "sample.json").write_text(
    json.dumps({"supported": False, "run_id": run_id}, indent=2), encoding="utf-8"
)
(unsupported / "sample.xml").write_text(
    f'<?xml version="1.0"?><demo><run>{run_id}</run></demo>', encoding="utf-8"
)
(unsupported / "sample.html").write_text(
    f"<!doctype html><html><body><p>Run {run_id}</p></body></html>", encoding="utf-8"
)
(unsupported / "sample.bin").write_bytes(run_id.encode("ascii") + os.urandom(4096))
with zipfile.ZipFile(unsupported / "sample.zip", "w") as archive:
    archive.writestr("inside.txt", f"Unsupported ZIP for run {run_id}\n")

print(f"Base files generated at {root}")
'@

$pythonOutput = $pythonCode | py -
if ($LASTEXITCODE -ne 0) {
    throw "Python dataset generation failed. Install dependencies with: py -m pip install Pillow reportlab python-docx"
}
$pythonOutput | ForEach-Object { Write-Host $_ }

$videoColor = $RunId.ToString("N").Substring(0, 6)
$supportedPath = Join-Path $OutputRoot "supported"
$wavPath = Join-Path $supportedPath "sample.wav"

& ffmpeg -hide_banner -loglevel error -y `
    -i $wavPath -codec:a libmp3lame -q:a 4 `
    (Join-Path $supportedPath "sample.mp3")
if ($LASTEXITCODE -ne 0) { throw "MP3 generation failed" }

& ffmpeg -hide_banner -loglevel error -y `
    -f lavfi -i "color=c=0x${videoColor}:size=640x360:rate=24" `
    -t 2 -metadata "comment=$RunId" -c:v mpeg4 -q:v 5 -pix_fmt yuv420p `
    (Join-Path $supportedPath "sample.mp4")
if ($LASTEXITCODE -ne 0) { throw "MP4 generation failed" }

& ffmpeg -hide_banner -loglevel error -y `
    -f lavfi -i "color=c=0x${videoColor}:size=640x360:rate=24" `
    -t 2 -metadata "comment=$RunId" -c:v mpeg4 -q:v 5 `
    (Join-Path $supportedPath "sample.avi")
if ($LASTEXITCODE -ne 0) { throw "AVI generation failed" }

& ffmpeg -hide_banner -loglevel error -y `
    -f lavfi -i "color=c=0x${videoColor}:size=640x360:rate=24" `
    -t 2 -metadata "comment=$RunId" -c:v mjpeg -q:v 5 `
    (Join-Path $supportedPath "sample.mov")
if ($LASTEXITCODE -ne 0) { throw "MOV generation failed" }

$files = Get-ChildItem -LiteralPath $OutputRoot -File -Recurse
$hashGroups = $files | Get-FileHash -Algorithm SHA256 | Group-Object Hash
# Force an array even when exactly one duplicate group is returned. Without
# @(...), PowerShell unwraps the single GroupInfo object and `.Count` below
# reports the number of files in that group instead of the number of groups.
$duplicateGroups = @($hashGroups | Where-Object Count -gt 1)

if ($files.Count -ne 19) {
    throw "Expected exactly 19 files, but generated $($files.Count)"
}
if ($duplicateGroups.Count -ne 1 -or $duplicateGroups[0].Count -ne 2) {
    throw "Expected exactly one two-file duplicate group"
}

[PSCustomObject]@{
    RunId = $RunId
    OutputRoot = $OutputRoot
    ObjectCount = $files.Count
    TotalBytes = ($files | Measure-Object Length -Sum).Sum
    IntentionalDuplicateHash = $duplicateGroups[0].Name
}

Remove-Item Env:INGESTION_DEMO_ROOT -ErrorAction SilentlyContinue
Remove-Item Env:INGESTION_DEMO_RUN_ID -ErrorAction SilentlyContinue
