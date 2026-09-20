"""Load the original Whisper checkpoint without duplicating all CPU weights.

The checkpoint stores FP16 tensors. Whisper's Linear/Conv1d already cast those
to the input dtype per layer; CPU inference still computes in FP32. Embeddings,
position buffers and LayerNorm parameters must be FP32 to preserve the standard
CPU loader's arithmetic. No quantization or smaller model is substituted.
"""
from pathlib import Path

import torch
from whisper.model import AudioEncoder, ModelDimensions, TextDecoder, Whisper


class MappedWhisper(Whisper):
    def __init__(self, dims):
        # Whisper.__init__ constructs a sparse alignment buffer, which has no
        # meta kernel. Build only its two large submodules on meta instead.
        torch.nn.Module.__init__(self)
        self.dims = dims
        with torch.device("meta"):
            self.encoder = AudioEncoder(dims.n_mels, dims.n_audio_ctx,
                                        dims.n_audio_state, dims.n_audio_head, dims.n_audio_layer)
            self.decoder = TextDecoder(dims.n_vocab, dims.n_text_ctx,
                                       dims.n_text_state, dims.n_text_head, dims.n_text_layer)
        self.decoder.mask = torch.full((dims.n_text_ctx, dims.n_text_ctx), -torch.inf).triu_(1)
        heads = torch.zeros(dims.n_text_layer, dims.n_text_head, dtype=torch.bool)
        heads[dims.n_text_layer // 2:] = True
        self.register_buffer("alignment_heads", heads.to_sparse(), persistent=False)


def load_cpu_checkpoint(path: Path, alignment_heads=None):
    checkpoint = torch.load(str(path), map_location="cpu", weights_only=True, mmap=True)
    model = MappedWhisper(ModelDimensions(**checkpoint["dims"]))
    model.load_state_dict(checkpoint["model_state_dict"], strict=True, assign=True)
    # These operations do not pass through Whisper's casting Linear/Conv1d.
    for module in model.modules():
        if isinstance(module, (torch.nn.LayerNorm, torch.nn.Embedding)):
            module.float()
    model.encoder.positional_embedding = model.encoder.positional_embedding.float()
    model.decoder.positional_embedding = torch.nn.Parameter(
        model.decoder.positional_embedding.float(), requires_grad=False)
    if alignment_heads is not None:
        model.set_alignment_heads(alignment_heads)
    return model.eval().requires_grad_(False)
