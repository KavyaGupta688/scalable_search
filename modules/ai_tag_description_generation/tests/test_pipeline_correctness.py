import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf
import torch
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline import model_manager
from modules.ai_tag_description_generation.worker.pipeline.captioning import (
    generate_text_description,
    generate_video_caption,
)
from modules.ai_tag_description_generation.worker.pipeline.document_processor import process_document
from modules.ai_tag_description_generation.worker.pipeline.image_processor import process_image
from modules.ai_tag_description_generation.worker.pipeline.retry_handler import TransientError
from modules.ai_tag_description_generation.worker.pipeline.confidence_validator import validate_and_score
from modules.ai_tag_description_generation.worker.pipeline.orchestrator import _derive_status
from modules.ai_tag_description_generation.worker.pipeline.quality_safety import PrivacySafetyLabels
from modules.ai_tag_description_generation.worker.pipeline.video_processor import _adjust_interval_for_cap
from modules.ai_tag_description_generation.worker.pipeline.tagging import (
    Tag,
    _aggregate_video_tags,
    _canonicalize_ram_label,
    _classify_ram_tag_category,
    _fine_grained_tags,
)


class PipelineCorrectnessTests(unittest.TestCase):
    def test_nsfw_adapter_ignores_faces_but_preserves_explicit_flags(self):
        from modules.ai_tag_description_generation.worker.pipeline.quality_safety import assess_nsfw
        image = Image.new('RGB', (8, 8))
        with patch.object(model_manager, 'get_model') as get_model:
            get_model.return_value.detect.return_value = [{'class':'FACE_MALE','score':0.99}]
            self.assertEqual(assess_nsfw([image]), 0)
            get_model.return_value.detect.return_value.append({'class':'FEMALE_BREAST_EXPOSED','score':0.9})
            self.assertEqual(assess_nsfw([image]), 0.9)

    def test_nsfw_failure_on_one_video_frame_cannot_clear_the_video(self):
        from modules.ai_tag_description_generation.worker.pipeline.quality_safety import assess_nsfw
        image = Image.new('RGB', (8, 8))
        with patch.object(model_manager, 'get_model') as get_model:
            get_model.return_value.detect.side_effect = [[], RuntimeError('frame failed')]
            with self.assertRaises(TransientError):
                assess_nsfw([image, image])

    @staticmethod
    def _high_confidence_record(safety_labels: dict) -> dict:
        return {
            "generated_tags": [{"confidence": 1.0}],
            "descriptions": {"short_description": "A complete description"},
            "extracted_text": {"ocr_text": {"confidence": 1.0}},
            "quality_labels": {"overall_quality": "good"},
            "safety_labels": safety_labels,
        }

    def test_pii_is_recorded_without_triggering_review(self) -> None:
        record = self._high_confidence_record({
            "contains_pii": True,
            "pii_types": ["face", "id_number", "license_plate"],
            "toxicity_score": 0.0,
            "nsfw_flagged": False,
            "analysis_incomplete": False,
        })

        validated, status = validate_and_score(record)

        self.assertEqual(status, "completed")
        self.assertTrue(validated["safety_labels"]["contains_pii"])

    def test_pii_does_not_trigger_review_in_fallback_status_routing(self) -> None:
        safety = PrivacySafetyLabels(contains_pii=True, pii_types=["face"])

        status = _derive_status(["quality_safety"], ["confidence_validation"], {
            "safety_labels": safety,
        })

        self.assertEqual(status, "partial")

    def test_nsfw_and_toxicity_still_trigger_review(self) -> None:
        for safety_labels in (
            {"nsfw_flagged": True, "toxicity_score": 0.0},
            {"nsfw_flagged": False, "toxicity_score": 1.0},
        ):
            with self.subTest(safety_labels=safety_labels):
                _, status = validate_and_score(self._high_confidence_record(safety_labels))
                self.assertEqual(status, "needs_review")

    def test_low_confidence_still_triggers_review(self) -> None:
        record = self._high_confidence_record({
            "nsfw_flagged": False,
            "toxicity_score": 0.0,
        })
        record["generated_tags"] = [{"confidence": 0.0}]
        record["descriptions"]["short_description"] = "short"
        record["extracted_text"] = {}

        _, status = validate_and_score(record)

        self.assertEqual(status, "needs_review")

    def test_incomplete_safety_is_never_cleared_by_pii_routing_change(self) -> None:
        from modules.shared.publication import safety_cleared
        labels = {"contains_pii": True, "analysis_incomplete": True, "toxicity_score": 0.0}
        _, status = validate_and_score(self._high_confidence_record(labels))
        self.assertEqual(status, "needs_review")
        self.assertFalse(safety_cleared(labels))
        self.assertEqual(_derive_status(["tagging"], ["confidence_validation"], {
            "safety_labels": PrivacySafetyLabels(**labels),
        }), "needs_review")

    def test_publication_policy_matches_pii_and_toxicity_routing(self) -> None:
        from modules.shared.publication import safety_cleared
        self.assertTrue(safety_cleared({"contains_pii": True, "analysis_incomplete": False}))
        for labels in ({}, {"nsfw_flagged": True}, {"analysis_incomplete": True},
                       {"toxicity_score": 0.8}, {"toxicity_score": float('nan')},
                       {"toxicity_score": "invalid"}):
            with self.subTest(labels=labels):
                self.assertFalse(safety_cleared(labels))

    def test_dynamic_text_does_not_reuse_another_documents_embedding(self) -> None:
        model_manager._text_embedding_cache.clear()
        with patch.object(
            model_manager,
            "encode_text",
            side_effect=[torch.tensor([[1.0]]), torch.tensor([[2.0]])],
        ) as encode:
            first = model_manager.get_text_embeddings("metadata", ["first document"])
            second = model_manager.get_text_embeddings("metadata", ["second document"])
            cached_first = model_manager.get_text_embeddings("metadata", ["first document"])

        self.assertEqual(encode.call_count, 2)
        self.assertEqual(first.item(), 1.0)
        self.assertEqual(second.item(), 2.0)
        self.assertEqual(cached_first.item(), 1.0)

    def test_image_processing_preserves_full_resolution_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "image.png"
            Image.new("RGB", (640, 360), "white").save(path)
            result = process_image(str(path))

        self.assertEqual(result.original_image.size, (640, 360))
        self.assertEqual(result.image.size, (224, 224))

    def test_blank_pdf_is_rendered_for_ocr(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scan.pdf"
            document = pymupdf.open()
            document.new_page(width=300, height=300)
            document.save(path)
            document.close()
            result = process_document(str(path))

        self.assertTrue(result.needs_ocr)
        self.assertEqual(len(result.pages_as_images), 1)

    def test_video_interval_respects_keyframe_cap(self) -> None:
        self.assertEqual(_adjust_interval_for_cap(41, 2), 3)

    def test_ram_action_lemmas_are_canonicalized(self) -> None:
        self.assertEqual(_classify_ram_tag_category("chase"), "action")
        self.assertEqual(_canonicalize_ram_label("chase"), "chasing")
        self.assertEqual(_classify_ram_tag_category("leash"), "attribute")

    def test_cartoon_video_rejects_uncorroborated_yolo_label(self) -> None:
        frames = [
            [
                Tag("cartoon", 0.75, "ram", "style"),
                Tag("dog", 0.75, "ram", "open_vocab"),
                Tag("leash", 0.75, "ram", "attribute"),
                Tag("kite", 0.90, "yolo", "object"),
            ],
            [
                Tag("cartoon", 0.75, "ram", "style"),
                Tag("dog", 0.75, "ram", "open_vocab"),
                Tag("leash", 0.75, "ram", "attribute"),
                Tag("kite", 0.88, "yolo", "object"),
            ],
        ]

        labels = {tag.label for tag in _aggregate_video_tags(frames)}

        self.assertIn("cartoon", labels)
        self.assertIn("dog", labels)
        self.assertNotIn("leash", labels)
        self.assertNotIn("kite", labels)

    def test_country_classifier_requires_explicit_flag_trigger(self) -> None:
        image = Image.new("RGB", (16, 16), "white")
        with patch(
            "modules.ai_tag_description_generation.worker.pipeline.tagging._clip_classify_crop",
            return_value=[],
        ) as classify:
            _fine_grained_tags(
                image,
                [Tag("city", 0.75, "ram", "scene"), Tag("outdoor", 0.75, "ram", "scene")],
                [],
            )
            classify.assert_not_called()

            _fine_grained_tags(
                image,
                [Tag("national flag", 0.75, "ram", "open_vocab")],
                [],
            )

        self.assertEqual(classify.call_count, 1)
        self.assertEqual(classify.call_args.args[1], "flag")

    def test_fine_grained_classifier_is_disabled_for_stylized_media(self) -> None:
        image = Image.new("RGB", (16, 16), "white")
        with patch(
            "modules.ai_tag_description_generation.worker.pipeline.tagging._clip_classify_crop"
        ) as classify:
            result = _fine_grained_tags(
                image,
                [Tag("cartoon", 0.75, "ram", "style"), Tag("dog", 0.75, "ram", "open_vocab")],
                [],
            )

        self.assertEqual(result, [])
        classify.assert_not_called()

    def test_video_caption_uses_multiple_frames_and_actions(self) -> None:
        frames = [Image.new("RGB", (16, 16), "white") for _ in range(5)]
        tags = [
            Tag("cartoon", 0.75, "ram", "style"),
            Tag("man", 0.75, "ram", "open_vocab"),
            Tag("dog", 0.75, "ram", "open_vocab"),
            Tag("chasing", 0.75, "ram", "action"),
        ]
        observations = [
            "a man walking a dog in a field",
            "a man playing with a cat",
            "a cartoon of a man and a dog",
            "a man walking on grass",
        ]
        with patch(
            "modules.ai_tag_description_generation.worker.pipeline.captioning.get_model",
            return_value={"model": object(), "processor": object()},
        ), patch(
            "modules.ai_tag_description_generation.worker.pipeline.captioning._generate",
            side_effect=observations,
        ) as generate:
            caption = generate_video_caption(frames, tags, duration_seconds=10.7)

        self.assertEqual(generate.call_count, 4)
        self.assertIn("cartoon video", caption.short_description)
        self.assertIn("man and a dog", caption.short_description)
        self.assertIn("dog", caption.short_description)
        self.assertIn("chasing", caption.long_description)
        self.assertTrue(caption.accessibility_description.startswith("[Video]"))
        self.assertNotIn("..", caption.accessibility_description)

    def test_caption_model_failure_is_not_reported_as_a_caption(self) -> None:
        with patch(
            "modules.ai_tag_description_generation.worker.pipeline.captioning.get_model",
            side_effect=RuntimeError("model unavailable"),
        ):
            with self.assertRaises(TransientError):
                generate_text_description("word " * 80, [], "document")

    def test_short_text_does_not_load_large_summarizer(self) -> None:
        with patch(
            "modules.ai_tag_description_generation.worker.pipeline.captioning.get_model"
        ) as get_model:
            caption = generate_text_description("A short factual transcript.", [], "audio")

        get_model.assert_not_called()
        self.assertEqual(caption.long_description, "A short factual transcript.")


if __name__ == "__main__":
    unittest.main()
