# worker/pipeline/preprocessing_engine.py
"""
Layer 5 - Preprocessing Engine.

The real orchestrator: routes a file via media_router, dispatches to the
matching processor, and returns one consistent result shape regardless of
modality. This is the single entry point the rest of the pipeline calls -
downstream code never touches individual processors directly.
"""

from dataclasses import dataclass
from typing import Any

from modules.ai_tag_description_generation.worker.pipeline.media_router import route_file, Modality, ModalityPolicy
from modules.ai_tag_description_generation.worker.pipeline import image_processor, video_processor, audio_processor, document_processor, csv_profiler


@dataclass
class PreprocessingResult:
    modality: Modality
    policy: ModalityPolicy
    data: Any                  # the specific processor's dataclass result (ProcessedImage, ProcessedVideo, etc.)
    error: str | None = None   # set if processing failed - lets the pipeline record partial status instead of crashing


def preprocess(file_path: str, file_type: str | None = None) -> PreprocessingResult:
    modality, policy = route_file(file_path, file_type)

    try:
        data = _dispatch(file_path, modality)
        return PreprocessingResult(modality=modality, policy=policy, data=data)
    except Exception as exc:
        # Preprocessing failures are data-quality issues (corrupt file,
        # unsupported codec, malformed CSV) as often as real bugs - don't
        # let one bad file crash the whole task. The caller (dispatcher)
        # decides whether this becomes a "partial" status or a retry.
        return PreprocessingResult(modality=modality, policy=policy, data=None, error=str(exc))


def _dispatch(file_path: str, modality: Modality) -> Any:
    if modality == Modality.IMAGE:
        return image_processor.process_image(file_path)
    if modality == Modality.VIDEO:
        return video_processor.process_video(file_path)
    if modality == Modality.AUDIO:
        return audio_processor.process_audio(file_path)
    if modality == Modality.DOCUMENT:
        return document_processor.process_document(file_path)
    if modality == Modality.CSV:
        return csv_profiler.process_csv(file_path)

    raise ValueError(f"No processor available for modality: {modality.value}")


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "sample.jpg"
    result = preprocess(path)

    print(f"Modality: {result.modality.value}")
    print(f"Policy: {result.policy}")
    if result.error:
        print(f"Error: {result.error}")
    else:
        print(f"Processed successfully: {type(result.data).__name__}")
        print(result.data)
