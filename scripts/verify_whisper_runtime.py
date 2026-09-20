"""Run actual Whisper STT against one authorized ingested audio document."""
import argparse
import json
from pathlib import Path
import resource
import time

from modules.ai_tag_description_generation.app.ingestion_client import get_document, materialize_document
from modules.ai_tag_description_generation.worker.pipeline.preprocessing_engine import preprocess
from modules.ai_tag_description_generation.worker.pipeline.ocr_stt import run_speech_to_text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document_id")
    parser.add_argument("--report", default="/models/provisioning/whisper-inference.json")
    args = parser.parse_args()
    started = time.monotonic()
    document = get_document(args.document_id)
    if not document.mime_type.startswith("audio/"):
        raise ValueError("This check requires an audio document")
    with materialize_document(document) as path:
        prep = preprocess(path, document.mime_type)
        if prep.error:
            raise ValueError(prep.error)
        result = run_speech_to_text(prep.data.waveform)
    assert not Path(path).exists(), "Temporary source bytes were not cleaned up"
    report = {"document_id": args.document_id, "ready": True,
              "seconds": round(time.monotonic() - started, 1),
              "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
              "text_characters": len(result.text), "language": result.language,
              "confidence": result.confidence, "temporary_source_removed": True}
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == "__main__":
    main()
