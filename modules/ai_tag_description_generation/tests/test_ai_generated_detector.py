import sys
import types
import unittest
from unittest.mock import patch

import torch
import torch.nn as nn
from PIL import Image

from modules.ai_tag_description_generation.worker.pipeline import model_manager


class AIGeneratedDetectorTests(unittest.TestCase):
    def test_builder_loads_official_checkpoint_on_runtime_device(self) -> None:
        calls = {}

        class FakeVit(nn.Module):
            def __init__(self):
                super().__init__()
                self.head = nn.Identity()

            def forward(self, image_batch):
                return torch.zeros((len(image_batch), 1))

        timm_module = types.ModuleType("timm")

        def create_model(name, pretrained):
            calls["architecture"] = name
            calls["pretrained"] = pretrained
            return FakeVit()

        timm_module.create_model = create_model

        class FakeHubMixin:
            @classmethod
            def from_pretrained(cls, model_id, **kwargs):
                calls["model_id"] = model_id
                calls["load_kwargs"] = kwargs
                return cls(device=kwargs["device"])

        hub_module = types.ModuleType("huggingface_hub")
        hub_module.PyTorchModelHubMixin = FakeHubMixin

        class IdentityTransform:
            def __init__(self, *args, **kwargs):
                pass

            def __call__(self, value):
                return value

        class Compose:
            def __init__(self, transforms):
                self.transforms = transforms

            def __call__(self, value):
                for transform in self.transforms:
                    value = transform(value)
                return value

        torchvision_module = types.ModuleType("torchvision")
        torchvision_module.transforms = types.SimpleNamespace(
            Compose=Compose,
            Resize=IdentityTransform,
            CenterCrop=IdentityTransform,
            ToTensor=IdentityTransform,
            Normalize=IdentityTransform,
        )

        with patch.dict(
            sys.modules,
            {
                "timm": timm_module,
                "huggingface_hub": hub_module,
                "torchvision": torchvision_module,
            },
        ):
            detector = model_manager._build_ai_generated_detector()

        self.assertIsInstance(detector, model_manager.AIGeneratedDetector)
        self.assertEqual(calls["model_id"], "OwensLab/commfor-model-384")
        self.assertEqual(calls["load_kwargs"]["device"], model_manager.DEVICE)
        self.assertEqual(calls["load_kwargs"]["map_location"], model_manager.DEVICE)
        self.assertTrue(calls["load_kwargs"]["strict"])
        self.assertEqual(
            calls["architecture"],
            "vit_small_patch16_384.augreg_in21k_ft_in1k",
        )
        self.assertFalse(calls["pretrained"])

    def test_community_forensics_detector_preserves_score_contract(self) -> None:
        calls = {}

        class FakeClassifier:
            def __call__(self, image_batch):
                calls["batch_shape"] = tuple(image_batch.shape)
                return torch.tensor([[2.0]])

        def preprocess(image):
            calls["mode"] = image.mode
            return torch.zeros((3, 384, 384))

        detector = model_manager.AIGeneratedDetector(
            FakeClassifier(), preprocess, device="cpu"
        )
        score = detector.score(Image.new("L", (32, 32)))

        self.assertEqual(calls["mode"], "RGB")
        self.assertEqual(calls["batch_shape"], (1, 3, 384, 384))
        self.assertAlmostEqual(score, torch.sigmoid(torch.tensor(2.0)).item())
        self.assertEqual(
            model_manager.MODEL_VERSIONS["ai_generated_detector"],
            model_manager.settings.AI_GENERATED_MODEL_NAME,
        )


if __name__ == "__main__":
    unittest.main()
