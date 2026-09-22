from modules.shared.embeddings import encode_text
from functools import lru_cache


class EmbeddingClient:
    def generate_text_embedding(self, text):
        return list(self._embedding(text))

    @lru_cache(maxsize=256)
    def _embedding(self, text):
        # Only deterministic model output is cached, never user-visible results.
        return tuple(encode_text([text])[0].detach().cpu().tolist())


@lru_cache
def get_embedding_client():
    return EmbeddingClient()
