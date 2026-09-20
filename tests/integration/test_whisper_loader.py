"""Exercise real Whisper layers on tiny weights; no model/network fixtures."""
from dataclasses import asdict

import pytest
import torch
from whisper.model import ModelDimensions, Whisper
from modules.ai_tag_description_generation.worker.pipeline.whisper_loader import load_cpu_checkpoint


def test_mapped_cpu_matches_standard_cpu_and_decoding_cache(tmp_path):
    torch.manual_seed(42)
    dims = ModelDimensions(4, 8, 8, 2, 2, 16, 8, 8, 2, 2)
    source = Whisper(dims)
    # Whisper leaves decoder positions uninitialized until checkpoint loading.
    torch.nn.init.normal_(source.decoder.positional_embedding, std=0.01)
    state = {k: v.half() for k, v in source.state_dict().items()}
    path = tmp_path / "test.pt"
    torch.save({"dims": asdict(dims), "model_state_dict": state}, path)
    standard = Whisper(dims).eval()
    standard.load_state_dict(state)
    mapped = load_cpu_checkpoint(path)
    assert mapped.encoder.conv1.weight.dtype == torch.float16
    assert mapped.encoder.ln_post.weight.dtype == torch.float32
    assert not any(p.is_meta or p.requires_grad for p in mapped.parameters())
    mel = torch.randn(1, 4, 16)
    tokens = torch.tensor([[1, 2, 3]])
    with torch.inference_mode():
        expected_audio, actual_audio = standard.embed_audio(mel), mapped.embed_audio(mel)
        torch.testing.assert_close(actual_audio, expected_audio, rtol=1e-5, atol=1e-6)
        torch.testing.assert_close(mapped.logits(tokens, actual_audio),
                                   standard.logits(tokens, expected_audio), rtol=1e-5, atol=1e-6)
        cache, hooks = mapped.install_kv_cache_hooks()
        try:
            mapped.decoder(tokens[:, :2], actual_audio, kv_cache=cache)
            incremental = mapped.decoder(tokens[:, 2:], actual_audio, kv_cache=cache)
            torch.testing.assert_close(incremental[:, -1], standard.logits(tokens, expected_audio)[:, -1],
                                       rtol=1e-5, atol=1e-6)
        finally:
            for hook in hooks:
                hook.remove()


def test_invalid_checkpoint_fails_closed(tmp_path):
    path = tmp_path / "bad.pt"
    torch.save({"dims": {}}, path)
    with pytest.raises((TypeError, KeyError)):
        load_cpu_checkpoint(path)


def test_single_cache_policy_releases_previous_model(monkeypatch):
    from modules.ai_tag_description_generation.worker.pipeline import model_manager as manager
    monkeypatch.setenv("AI_MODEL_CACHE_POLICY", "single")
    monkeypatch.setattr(manager, "_model_cache", {})
    first, second = object(), object()
    monkeypatch.setattr(manager, "_load_yolo", lambda: first)
    monkeypatch.setattr(manager, "_load_blip", lambda: second)
    assert manager.get_model("yolo") is first
    assert manager.get_model("yolo") is first
    assert manager.get_model("blip") is second
    assert manager._model_cache == {"blip": second}


def test_execution_slot_excludes_other_worker_and_cleans_up_on_failure(monkeypatch, tmp_path):
    from filelock import FileLock, Timeout
    from modules.ai_tag_description_generation.worker.pipeline import model_manager as manager
    path = str(tmp_path / "inference.lock")
    monkeypatch.setenv("AI_MODEL_EXECUTION_LOCK", path)
    monkeypatch.setenv("AI_MODEL_CACHE_POLICY", "single")
    monkeypatch.setattr(manager, "_model_cache", {"test": object()})
    with pytest.raises(RuntimeError, match="stage failed"):
        with manager.model_execution_slot():
            with pytest.raises(Timeout):
                with FileLock(path, timeout=0):
                    pass
            raise RuntimeError("stage failed")
    assert manager._model_cache == {}
    with FileLock(path, timeout=0):
        pass
