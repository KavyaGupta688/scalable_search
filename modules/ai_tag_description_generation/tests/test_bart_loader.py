import pytest
import torch
from types import SimpleNamespace
from transformers import BartConfig, BartForSequenceClassification, BartForConditionalGeneration
from modules.ai_tag_description_generation.worker.pipeline.model_manager import _load_bart_pipeline


@pytest.mark.parametrize('task,model_class', [
    ('zero-shot-classification', BartForSequenceClassification),
    ('summarization', BartForConditionalGeneration),
])
@pytest.mark.parametrize('decoder_only', [False, True])
def test_low_memory_bart_preserves_tied_weights_and_inference(tmp_path, monkeypatch, task, model_class, decoder_only):
    config = BartConfig(vocab_size=32, d_model=8, encoder_layers=1, decoder_layers=1,
                        encoder_attention_heads=2, decoder_attention_heads=2,
                        encoder_ffn_dim=16, decoder_ffn_dim=16, max_position_embeddings=32,
                        num_labels=3)
    reference = model_class(config).eval()
    state = reference.state_dict()
    if decoder_only:
        # Original BART-CNN layout keeps only one of the tied embedding aliases.
        state = {k: v for k, v in state.items() if k not in {
            'model.shared.weight', 'model.encoder.embed_tokens.weight', 'lm_head.weight'}}
    reference.save_pretrained(tmp_path, state_dict=state, safe_serialization=not decoder_only)
    tokenizer = SimpleNamespace(model_max_length=1024)
    monkeypatch.setattr('transformers.AutoTokenizer.from_pretrained', lambda *a, **k: tokenizer)
    monkeypatch.setattr('transformers.pipeline', lambda *args, **kwargs: kwargs['model'])
    loaded = _load_bart_pipeline(task, str(tmp_path)).eval()
    assert tokenizer.model_max_length == 32
    assert not any(p.is_meta for p in loaded.parameters())
    shared = loaded.get_input_embeddings()
    assert loaded.model.encoder.embed_tokens is shared
    assert loaded.model.decoder.embed_tokens is shared
    for key, value in reference.state_dict().items():
        assert torch.equal(value, loaded.state_dict()[key]), key
    inputs = torch.tensor([[0, 5, 6, 2]])
    with torch.no_grad():
        assert torch.allclose(reference(inputs).logits, loaded(inputs).logits, atol=1e-6)
