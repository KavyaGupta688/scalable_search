"""Verify detector scores and failures reach the enrichment safety labels."""

from unittest.mock import Mock, patch

import pytest
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline import quality_safety as safety


def test_empty_images_do_not_load_detector():
    with patch.object(safety.model_manager, "get_model") as load:
        assert safety.assess_ai_generated([]) == 0.0
    load.assert_not_called()


def test_multiple_frames_keep_highest_score_despite_one_failed_frame():
    detector = Mock()
    detector.score.side_effect = [0.1, RuntimeError("bad frame"), 0.9]
    with patch.object(safety.model_manager, "get_model", return_value=detector):
        assert safety.assess_ai_generated([object(), object(), object()]) == 0.9


@pytest.mark.parametrize("load_fails", [False, True])
def test_detector_failure_is_retryable(load_fails):
    detector = Mock()
    detector.score.side_effect = RuntimeError("inference failed")
    with patch.object(
        safety.model_manager, "get_model", return_value=detector,
        side_effect=RuntimeError("checkpoint unavailable") if load_fails else None,
    ):
        with pytest.raises(safety.TransientError):
            safety.assess_ai_generated([object()])


@pytest.mark.parametrize("score,flagged", [(0.49, False), (0.5, True), (0.9, True)])
@pytest.mark.parametrize("modality", ["IMAGE", "VIDEO", "DOCUMENT"])
def test_pipeline_applies_threshold_and_preserves_score(score, flagged, modality):
    image = Image.new("RGB", (32, 32))
    detector = Mock()
    detector.score.return_value = score
    with (
        patch.object(safety.model_manager, "get_model", return_value=detector),
        patch.object(safety, "detect_pii_in_text", return_value=safety.PrivacySafetyLabels()),
        patch.object(safety, "detect_pii_in_images", return_value=safety.PrivacySafetyLabels()),
        patch.object(safety, "assess_nsfw", return_value=0.0),
        patch.object(safety, "assess_toxicity", return_value=0.0),
        patch.object(safety.settings, "AI_GENERATED_THRESHOLD", 0.5),
    ):
        key = "keyframes" if modality == "VIDEO" else "images"
        _, labels = safety.run_quality_safety_pipeline({key: [image]}, {}, modality)
    assert labels.ai_generated_score == score
    assert labels.ai_generated_flagged is flagged
    assert not labels.analysis_incomplete
