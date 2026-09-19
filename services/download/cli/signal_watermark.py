"""Local JPEG, PNG, WAV and FLAC signal watermark tools (no S3/database needed)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import CODEC_WATERMARK_SECRET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("embed", "extract"))
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--download-id")
    parser.add_argument("--native", choices=("mp3", "aac", "m4a", "video"), help="Explicit native codec backend")
    args = parser.parse_args()
    if len(CODEC_WATERMARK_SECRET.encode()) < 32:
        parser.error("Set CODEC_WATERMARK_SECRET to a private key of at least 32 bytes")
    if args.source.stat().st_size > 64 * 1024 * 1024:
        parser.error("Input exceeds 64 MiB")
    data = args.source.read_bytes()
    try:
        if args.operation == "extract":
            from core.codec_forensics import inspect_signal
            report = inspect_signal(data)
            if report and report.get("authenticated"):
                print(f"{report['method']}: {report['download_id']}")
                return 0
            print(report or "Unsupported signal format")
            return 1
        if not args.output or not args.download_id:
            parser.error("embed requires --output and --download-id")
        if args.output.exists():
            parser.error("Output exists; choose a new filename")
        if args.native == "mp3":
            from core.native_mp3 import embed_bytes
        elif args.native in ("aac", "m4a"):
            from core.native_aac import embed_bytes as aac_embed
            embed_bytes = lambda data, uid, key: aac_embed(data, uid, key, "ipod" if args.native == "m4a" else "adts")
        elif args.native == "video":
            from core.native_video import embed_bytes
        elif data.startswith(b"\xff\xd8"):
            from core.codec_jpeg import embed_bytes
        elif data.startswith(b"\x89PNG"):
            from core.signal_png import embed_bytes
        elif data.startswith(b"fLaC") or (data.startswith(b"RIFF") and data[8:12] == b"WAVE"):
            from core.signal_audio import embed_bytes
        else:
            parser.error("Choose --native for MP3/AAC/video, or supply JPEG, PNG, WAV or FLAC")
        result = embed_bytes(data, args.download_id, CODEC_WATERMARK_SECRET)
        with args.output.open("xb") as output:
            output.write(result)
        print(f"Embedded and verified: {args.output}")
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
