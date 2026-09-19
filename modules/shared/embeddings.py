"""The same CLIP space for query and document embeddings."""

from functools import lru_cache


@lru_cache
def clip_bundle():
    import open_clip
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32", pretrained="openai", force_quick_gelu=True
    )
    return {
        "model": model.to(device).eval(),
        "preprocess": preprocess,
        "tokenizer": open_clip.get_tokenizer("ViT-B-32"),
        "device": device,
    }


def encode_text(texts):
    import torch

    bundle = clip_bundle()
    model, tokenizer, device = bundle["model"], bundle["tokenizer"], bundle["device"]
    with torch.no_grad():
        vectors = model.encode_text(tokenizer(texts).to(device))
        return vectors / vectors.norm(dim=-1, keepdim=True).clamp_min(1e-12)
