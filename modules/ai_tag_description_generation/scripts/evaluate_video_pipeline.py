"""Run the video AI stages locally without PostgreSQL, Redis, ingestion API, or Qdrant."""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from modules.ai_tag_description_generation.worker.pipeline.captioning import generate_video_caption
from modules.ai_tag_description_generation.worker.pipeline.tagging import generate_all_tags
from modules.ai_tag_description_generation.worker.pipeline.video_processor import process_video


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    args = parser.parse_args()

    processed = process_video(args.video)
    tags = generate_all_tags(processed.keyframes, None, "video")
    caption = generate_video_caption(
        processed.keyframes,
        tags,
        duration_seconds=processed.duration_seconds,
    )
    print(json.dumps({
        "duration_seconds": processed.duration_seconds,
        "keyframes": len(processed.keyframes),
        "tags": [tag.__dict__ for tag in tags],
        "caption": caption.__dict__,
    }, indent=2))


if __name__ == "__main__":
    main()
