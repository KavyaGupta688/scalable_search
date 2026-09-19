"""Generate tiny, synthetic acceptance sources; never runs in the application."""

import csv, subprocess, wave
from pathlib import Path
from PIL import Image, ImageDraw

root = Path("/fixtures")
root.mkdir(parents=True, exist_ok=True)
image = Image.new("RGB", (160, 120), "white")
ImageDraw.Draw(image).rectangle((30, 20, 100, 90), fill="blue")
image.save(root / "blue-square.png")
image.save(root / "document.pdf", "PDF")
(root / "table.csv").write_text("category,value\nblue,2\ngreen,3\n")
with wave.open(str(root / "silence.wav"), "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(16000)
    wav.writeframes(b"\0" * 32000)
subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=160x120:d=1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(root / "blue-video.mp4"),
    ],
    check=True,
    capture_output=True,
)
with (root / "metadata.csv").open("w", newline="") as stream:
    writer = csv.writer(stream)
    writer.writerow(["id", "filename", "title", "category", "tags"])
    for i, p in enumerate(sorted(root.iterdir())):
        if p.name != "metadata.csv":
            writer.writerow(
                [str(i), p.name, "Acceptance " + p.stem, "Acceptance", "blue|synthetic"]
            )
print("Created five bounded source fixtures and vendor metadata")
