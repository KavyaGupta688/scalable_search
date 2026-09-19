"""Standalone native JPEG embedding and authenticated extraction."""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.codec_jpeg import embed_file, extract_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("embed", "extract"))
    parser.add_argument("source")
    parser.add_argument("--output")
    parser.add_argument("--download-id")
    args = parser.parse_args()
    secret = os.environ.get("CODEC_WATERMARK_SECRET", "")
    if len(secret.encode()) < 32:
        parser.error("Set CODEC_WATERMARK_SECRET to a private random secret of at least 32 bytes")
    try:
        if args.operation == "embed":
            if not args.output or not args.download_id:
                parser.error("embed requires --output and --download-id")
            if Path(args.output).exists():
                parser.error("Output already exists; choose a new filename")
            embed_file(args.source, args.output, args.download_id, secret)
            recovered = extract_file(args.output, secret)
            if recovered != args.download_id.lower():
                raise ValueError("Post-write extraction failed")
            print(f"Embedded and verified download ID: {recovered}")
        else:
            recovered = extract_file(args.source, secret)
            print(f"Authenticated download ID: {recovered}" if recovered else "No authenticated watermark recovered")
            return 0 if recovered else 1
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
