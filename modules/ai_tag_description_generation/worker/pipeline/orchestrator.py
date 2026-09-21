# worker/pipeline/orchestrator.py
"""
Pipeline Orchestrator — the main entry point for enrichment processing.

Executes stages 1→11 sequentially per file, wrapping each stage with
checkpoint writes, retry logic, and partial-success accumulation. A
failure in one stage doesn't block subsequent stages — the pipeline
collects whatever outputs succeed and assigns a final status accordingly.
"""

import logging
import json
import time
import uuid
import traceback
from datetime import datetime, timezone
from typing import Any

from modules.ai_tag_description_generation.worker.pipeline import task_dispatcher
from modules.ai_tag_description_generation.worker.pipeline.retry_handler import TransientError, DataQualityError
from modules.ai_tag_description_generation.worker.pipeline.preprocessing_engine import preprocess, PreprocessingResult
from modules.ai_tag_description_generation.worker.pipeline import technical_metadata
from modules.ai_tag_description_generation.worker.pipeline.media_router import Modality
from modules.ai_tag_description_generation.worker.pipeline import ocr_stt
from modules.ai_tag_description_generation.worker.pipeline import tagging as tagging_module
from modules.ai_tag_description_generation.worker.pipeline import captioning as captioning_module
from modules.ai_tag_description_generation.worker.pipeline import quality_safety
from modules.ai_tag_description_generation.worker.pipeline import metadata_fusion
from modules.ai_tag_description_generation.worker.pipeline import confidence_validator
from modules.ai_tag_description_generation.worker.pipeline import metadata_persistence
from modules.ai_tag_description_generation.worker.pipeline.model_manager import get_model_version_string, MODEL_VERSIONS
from modules.ai_tag_description_generation.app.config import settings
from modules.ai_tag_description_generation.app.ingestion_client import IngestionDocument
from modules.ai_tag_description_generation.app.event_publisher import publish_enrichment_event
from modules.ai_tag_description_generation.app.event_schemas import (
    EnrichmentCompletedEvent, EnrichmentPartialEvent,
    NeedsReviewEvent, EnrichmentFailedEvent, ProcessingSummary,
)

logger = logging.getLogger(__name__)

PIPELINE_STAGES = task_dispatcher.PIPELINE_STAGES


def run_enrichment_pipeline(
    document: IngestionDocument,
    processing_path: str,
) -> str:
    """Execute the full enrichment pipeline for a single file. Returns final status."""

    file_id = document.document_id
    storage_path = document.source_ref or document.document_id
    file_type = document.mime_type
    source_metadata = document.metadata

    # --- Stage 1: Task Dispatch ---
    task, resume_stage = task_dispatcher.dispatch_or_resume(document)

    if resume_stage is None:
        # Task is already completed or terminally failed — nothing to do.
        logger.info(f"[{file_id}] Skipping: task status is already '{task.status}'")
        return task.status

    # --- Acquire lock to prevent duplicate processing ---
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    if not task_dispatcher.acquire_lock(file_id, worker_id, settings.TASK_LOCK_TTL_SECONDS):
        logger.warning(f"[{file_id}] Could not acquire lock — another worker is processing this file")
        return "skipped"

    pipeline_start = time.time()

    try:
        task_dispatcher.transition_status(file_id, "in_progress")

        # ctx accumulates results across stages — each stage reads from
        # and writes to this dict so later stages can use earlier outputs.
        ctx: dict[str, Any] = {
            "file_id": file_id,
            "storage_path": storage_path,
            "file_type": file_type,
            "source_metadata": source_metadata,
            "source_asset_id": document.source_asset_id,
            "run_id": document.run_id,
            "entitlement_id": document.entitlement_id,
        }

        start_idx = PIPELINE_STAGES.index(resume_stage) if resume_stage in PIPELINE_STAGES else 0
        stages_completed: list[str] = []
        stages_failed: list[str] = []

        local_path = processing_path
        for stage_name in PIPELINE_STAGES[start_idx:]:
            if not task_dispatcher.acquire_lock(file_id, worker_id, settings.TASK_LOCK_TTL_SECONDS):
                raise RuntimeError("Processing lock was lost")
            task_dispatcher.update_stage(file_id, stage_name, "started")
            stage_start = time.time()

            try:
                _execute_stage(stage_name, file_id, local_path, file_type, ctx)
                duration_ms = int((time.time() - stage_start) * 1000)
                task_dispatcher.update_stage(file_id, stage_name, "completed", duration_ms=duration_ms)
                stages_completed.append(stage_name)

            except DataQualityError as exc:
                # Data-quality issues are NOT retried — store as partial
                # and continue to the next stage.
                duration_ms = int((time.time() - stage_start) * 1000)
                task_dispatcher.update_stage(file_id, stage_name, "failed", error=str(exc), duration_ms=duration_ms)
                stages_failed.append(stage_name)
                logger.warning(f"[{file_id}] Stage '{stage_name}' data-quality failure: {exc}")

            except TransientError as exc:
                # Persist the failed checkpoint, then let Celery retry the
                # whole task with backoff.
                duration_ms = int((time.time() - stage_start) * 1000)
                task_dispatcher.update_stage(file_id, stage_name, "failed", error=str(exc), duration_ms=duration_ms)
                stages_failed.append(stage_name)
                logger.error(f"[{file_id}] Stage '{stage_name}' transient failure after retries: {exc}")
                raise

            except Exception as exc:
                duration_ms = int((time.time() - stage_start) * 1000)
                task_dispatcher.update_stage(file_id, stage_name, "failed", error=str(exc), duration_ms=duration_ms)
                stages_failed.append(stage_name)
                logger.error(f"[{file_id}] Stage '{stage_name}' unexpected error:\n{traceback.format_exc()}")

        # --- Determine final status ---
        total_duration = time.time() - pipeline_start

        # Use the confidence validator's verdict if available, otherwise
        # derive status from which stages passed/failed.
        final_status = ctx.get("final_status", _derive_status(stages_completed, stages_failed, ctx))

        task_dispatcher.transition_status(file_id, final_status, error_message=(
            f"Failed stages: {stages_failed}" if stages_failed else None
        ))

        # --- Stage 11: Event Publication ---
        _publish_result_event(
            file_id, final_status, stages_completed, stages_failed, total_duration, ctx
        )

        logger.info(
            f"[{file_id}] Pipeline finished: status={final_status}, "
            f"completed={len(stages_completed)}/{len(PIPELINE_STAGES)}, "
            f"duration={total_duration:.1f}s"
        )
        return final_status

    finally:
        task_dispatcher.release_lock(file_id, worker_id)


# ---------------------------------------------------------------------------
# Stage execution functions
# ---------------------------------------------------------------------------

def _execute_stage(stage_name: str, file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    """Dispatch to the correct stage function. Wraps transient-prone stages with retry."""
    stage_fn = STAGE_FUNCTIONS.get(stage_name)
    if stage_fn is None:
        logger.warning(f"[{file_id}] No handler for stage '{stage_name}', skipping")
        return
    stage_fn(file_id, storage_path, file_type, ctx)


def _run_preprocessing(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    result: PreprocessingResult = preprocess(storage_path, file_type)
    if result.error:
        raise DataQualityError(f"Preprocessing failed: {result.error}")
    ctx["preprocessing_result"] = result
    ctx["modality"] = result.modality


def _run_ocr_extraction(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    prep = ctx.get("preprocessing_result")
    if prep is None:
        raise DataQualityError("No preprocessing result available for OCR/STT")

    modality = prep.modality
    data = prep.data

    # Build the dict that ocr_stt.extract_text_for_modality expects
    preprocessing_dict: dict[str, Any] = {}
    if modality == Modality.IMAGE:
        preprocessing_dict["images"] = [data.original_image]
    elif modality == Modality.VIDEO:
        preprocessing_dict["keyframes"] = data.keyframes
        preprocessing_dict["audio_waveform"] = data.audio_waveform
    elif modality == Modality.AUDIO:
        preprocessing_dict["audio_waveform"] = data.waveform
    elif modality == Modality.DOCUMENT:
        preprocessing_dict["text"] = data.full_text
        preprocessing_dict["needs_ocr"] = data.needs_ocr
        preprocessing_dict["pages_as_images"] = data.pages_as_images
    elif modality == Modality.CSV:
        col_names = [c.name for c in data.columns]
        sample_str = str(data.sample_rows[:3]) if data.sample_rows else ""
        preprocessing_dict["columns"] = col_names
        preprocessing_dict["sample_data"] = sample_str

    extracted = ocr_stt.extract_text_for_modality(preprocessing_dict, modality.value.upper())
    ctx["extracted_text"] = extracted


def _vendor_context_text(metadata: dict, limit: int = 16_000) -> str:
    """Semantic fallback only; identifiers and arbitrary metadata are not content."""
    if not isinstance(metadata, dict):
        return ""
    fields = (
        "title",
        "description",
        "primary_category",
        "tags",
        "categories",
        "brand",
    )
    parts: list[str] = []
    for name in fields:
        value = metadata.get(name)
        if value in (None, "", [], {}):
            continue
        rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        parts.append(rendered)
    return "\n".join(parts)[:limit]


def _run_tagging(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    prep = ctx.get("preprocessing_result")
    modality = ctx.get("modality", Modality.UNKNOWN)
    extracted = ctx.get("extracted_text", {})

    # Gather any extracted text for text-based tagging
    text_pieces: list[str] = []
    for key in ("ocr_text", "transcribed_text", "native_document_text"):
        result = extracted.get(key)
        if result is not None and result.text:
            text_pieces.append(result.text)
    combined_text = " ".join(text_pieces) if text_pieces else None
    vendor_context = _vendor_context_text(ctx.get("source_metadata") or {})
    if not combined_text and modality not in (Modality.IMAGE, Modality.VIDEO):
        combined_text = vendor_context or None

    # Gather images for vision-based tagging
    images: list = []
    if prep and prep.data:
        if modality == Modality.IMAGE:
            images = [prep.data.original_image]
        elif modality == Modality.VIDEO:
            images = prep.data.keyframes

    tags = tagging_module.generate_all_tags(
        images=images or None,
        text=combined_text,
        modality_str=modality.value,
    )
    ctx["tags"] = tags


def _run_captioning(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    prep = ctx.get("preprocessing_result")
    tags = ctx.get("tags", [])
    extracted = ctx.get("extracted_text", {})
    modality = ctx.get("modality", Modality.UNKNOWN)

    # Combine OCR and speech instead of discarding everything after the first
    # non-empty extraction result.
    text_pieces: list[str] = []
    for key in ("ocr_text", "transcribed_text", "native_document_text"):
        result = extracted.get(key)
        if result is not None and result.text:
            text_pieces.append(result.text)
    supporting_text = " ".join(text_pieces)
    # Vision captions must not mislabel vendor metadata as extracted OCR/speech.
    # Text modalities prefer actual content; vendor context is an explicit fallback.
    vendor_fallback = not supporting_text and modality not in (Modality.IMAGE, Modality.VIDEO)
    if vendor_fallback:
        supporting_text = _vendor_context_text(ctx.get("source_metadata") or {})

    # Route to the right captioning function based on modality
    if modality == Modality.VIDEO and prep and prep.data and prep.data.keyframes:
        caption = captioning_module.generate_video_caption(
            prep.data.keyframes,
            tags,
            supporting_text,
            prep.data.duration_seconds,
        )
    elif modality == Modality.IMAGE:
        if prep and prep.data:
            image = prep.data.original_image
        else:
            image = None

        if image is not None:
            ocr_text = supporting_text
            caption = captioning_module.generate_caption(image, tags, ocr_text)
        else:
            caption = captioning_module.generate_text_description(supporting_text, tags, modality.value)
    else:
        caption = captioning_module.generate_text_description(
            supporting_text, tags, modality.value
        )

    if vendor_fallback and supporting_text:
        caption.short_description = "Vendor context: " + caption.short_description
        caption.long_description = "Vendor context (no extracted text): " + caption.long_description
    ctx["caption"] = caption


def _run_quality_safety(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    prep = ctx.get("preprocessing_result")
    extracted = ctx.get("extracted_text", {})
    modality = ctx.get("modality", Modality.UNKNOWN)
    if prep is None or prep.data is None or modality == Modality.UNKNOWN:
        raise DataQualityError("Source preprocessing unavailable; safety cannot be assessed")

    # Build the dict quality_safety expects
    preprocessing_dict: dict[str, Any] = {}
    if prep and prep.data:
        if modality == Modality.IMAGE:
            preprocessing_dict["images"] = [prep.data.original_image]
        elif modality == Modality.VIDEO:
            preprocessing_dict["keyframes"] = prep.data.keyframes
        elif modality == Modality.AUDIO:
            preprocessing_dict["audio_waveform"] = prep.data.waveform
        elif modality == Modality.DOCUMENT:
            preprocessing_dict["images"] = prep.data.pages_as_images

    q_labels, s_labels = quality_safety.run_quality_safety_pipeline(
        preprocessing_dict, extracted, modality.value.upper()
    )
    if modality == Modality.IMAGE and getattr(prep.data, "frame_count", 1) > 1:
        s_labels.analysis_incomplete = True
        s_labels.analysis_errors.append("Animated image: only the first frame was analyzed")
    ctx["quality_labels"] = q_labels
    ctx["safety_labels"] = s_labels


def _run_metadata_fusion(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    tags = ctx.get("tags", [])
    caption = ctx.get("caption")
    extracted = ctx.get("extracted_text", {})
    q_labels = ctx.get("quality_labels")
    s_labels = ctx.get("safety_labels")
    modality = ctx.get("modality", Modality.UNKNOWN)

    # Convert Tag dataclasses to dicts for the fusion module
    tag_dicts = [
        {"tag": t.label, "category": t.category, "source_model": t.source, "confidence": t.confidence}
        for t in tags
    ] if tags else []

    caption_dict = {}
    if caption:
        caption_dict = {
            "short": caption.short_description,
            "long": caption.long_description,
            "search": caption.search_description,
            "alt": caption.accessibility_description,
        }

    from modules.ai_tag_description_generation.worker.pipeline.quality_safety import QualityLabels, PrivacySafetyLabels
    if q_labels is None:
        q_labels = QualityLabels(blur_score=1.0, is_blurry=False, low_light=False, noisy_audio=False, overall_quality="good")
    if s_labels is None:
        s_labels = PrivacySafetyLabels(
            analysis_incomplete=True,
            analysis_errors=["Quality and safety stage did not complete"],
        )

    fused = metadata_fusion.fuse_metadata(
        tags=tag_dicts,
        captions=caption_dict,
        extracted_text=extracted,
        quality_labels=q_labels,
        safety_labels=s_labels,
        modality=modality.value,
        model_versions=MODEL_VERSIONS,
        technical=technical_metadata.from_preprocessing(ctx.get("preprocessing_result")),
    )
    ctx["fused_metadata"] = fused


def _run_confidence_validation(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    fused = ctx.get("fused_metadata")
    if fused is None:
        raise DataQualityError("No fused metadata available for validation")

    validated_record, final_status = confidence_validator.validate_and_score(fused)
    ctx["fused_metadata"] = validated_record
    ctx["final_status"] = final_status


def _run_persistence(file_id: str, storage_path: str, file_type: str, ctx: dict) -> None:
    fused = ctx.get("fused_metadata")
    if fused is None:
        raise DataQualityError("No metadata to persist")

    model_version = get_model_version_string()
    enrichment_version = settings.ENRICHMENT_VERSION

    # Flatten the fused payload into DocumentEnrichmentMetadata columns.
    # Keep OCR, transcription, and native document text distinct so callers
    # can retrieve the appropriate source without parsing a JSON envelope.
    extracted_text = fused.get("extracted_text", {})
    persist_dict = {
        "source_asset_id": ctx.get("source_asset_id"),
        "run_id": ctx.get("run_id"),
        "correlation_id": ctx.get("run_id"),
        "generated_tags": fused.get("generated_tags"),
        "short_description": fused.get("descriptions", {}).get("short_description", ""),
        "long_description": fused.get("descriptions", {}).get("long_description", ""),
        "search_description": fused.get("descriptions", {}).get("search_optimized", ""),
        "accessibility_description": fused.get("descriptions", {}).get("accessibility_alt", ""),
        "ocr_text": (extracted_text.get("ocr_text") or {}).get("text"),
        "transcribed_text": (extracted_text.get("transcribed_text") or {}).get("text"),
        "native_document_text": (extracted_text.get("native_document_text") or {}).get("text"),
        "privacy_safety_labels": fused.get("safety_labels"),
        "restricted_metadata": fused.get("restricted_metadata"),
        "quality_labels": fused.get("quality_labels"),
        "confidence_scores": fused.get("confidence_scores"),
        "model_versions": fused.get("models_used"),
        "status": ctx.get("final_status", "completed"),
    }

    record_id = metadata_persistence.persist_metadata(
        file_id, persist_dict, model_version, enrichment_version
    )
    ctx["persisted_record_id"] = record_id

    # Qdrant is part of persistence; a failure must be retried.
    metadata_persistence.forward_for_embedding(file_id, persist_dict)


STAGE_FUNCTIONS = {
    "preprocessing": _run_preprocessing,
    "ocr_extraction": _run_ocr_extraction,
    "tagging": _run_tagging,
    "captioning": _run_captioning,
    "quality_safety": _run_quality_safety,
    "metadata_fusion": _run_metadata_fusion,
    "confidence_validation": _run_confidence_validation,
    "persistence": _run_persistence,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_status(stages_completed: list[str], stages_failed: list[str], ctx: dict) -> str:
    """Derive the final status when the confidence validator didn't run."""
    if not stages_completed and stages_failed:
        return "failed_terminal"
    if stages_failed:
        safety = ctx.get("safety_labels")
        if safety and (
            safety.nsfw_flagged
            or safety.toxicity_score >= settings.TOXICITY_THRESHOLD
            or safety.analysis_incomplete
        ):
            return "needs_review"
        aggregate = (
            ctx.get("fused_metadata", {})
            .get("confidence_scores", {})
            .get("aggregate")
        )
        if aggregate is not None and aggregate < settings.CONFIDENCE_THRESHOLD_REVIEW:
            return "needs_review"
        return "partial"
    return "completed"


def _publish_result_event(
    file_id: str,
    final_status: str,
    stages_completed: list[str],
    stages_failed: list[str],
    duration_seconds: float,
    ctx: dict,
) -> None:
    """Build and publish the right enrichment event based on final status."""
    tags = ctx.get("tags", [])
    safety = ctx.get("safety_labels")
    fused = ctx.get("fused_metadata", {})

    summary = ProcessingSummary(
        stages_completed=stages_completed,
        stages_failed=stages_failed,
        duration_seconds=round(duration_seconds, 2),
        tags_generated=len(tags),
        pii_detected=safety.contains_pii if safety else False,
        nsfw_flagged=safety.nsfw_flagged if safety else False,
    )

    common = dict(
        document_id=file_id,
        source_asset_id=ctx.get("source_asset_id"),
        run_id=ctx.get("run_id"),
        metadata_version="1.0",
        model_version=get_model_version_string(),
        enrichment_version=settings.ENRICHMENT_VERSION,
        confidence_aggregate=fused.get("confidence_scores", {}).get("aggregate", 0.0),
        processing_summary=summary,
        timestamp=datetime.now(timezone.utc),
    )

    try:
        if final_status == "completed":
            event = EnrichmentCompletedEvent(**common)
        elif final_status == "partial":
            event = EnrichmentPartialEvent(**common, failed_stages=stages_failed)
        elif final_status == "needs_review":
            reasons = []
            if safety and safety.nsfw_flagged:
                reasons.append("NSFW content detected")
            if safety and safety.toxicity_score >= settings.TOXICITY_THRESHOLD:
                reasons.append("Toxic content detected")
            if safety and safety.analysis_incomplete:
                reasons.append("One or more safety checks did not complete")
            if fused.get("confidence_scores", {}).get("aggregate", 1.0) < settings.CONFIDENCE_THRESHOLD_REVIEW:
                reasons.append("Low confidence score")
            event = NeedsReviewEvent(**common, review_reasons=reasons or ["Manual review requested"])
        else:
            event = EnrichmentFailedEvent(
                **common,
                error_details=f"Failed stages: {stages_failed}",
            )
        publish_enrichment_event(event)
    except Exception as exc:
        # Event publication failure should never crash the pipeline — the
        # DB is the source of truth, events are best-effort notifications.
        logger.error(f"[{file_id}] Failed to publish enrichment event: {exc}")


if __name__ == "__main__":
    raise SystemExit("Run through the API, Celery worker, or Kafka consumer")
