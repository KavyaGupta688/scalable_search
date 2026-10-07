from modules.shared.embeddings import encode_text
from functools import lru_cache
import hashlib
import logging
import os
import time

import numpy as np

logger = logging.getLogger(__name__)

# Shared across Search replicas so a query embedded once is not re-embedded elsewhere.
# Keys name the model, so a model change never reuses old vectors.
_REDIS_TTL = int(os.getenv("SEARCH_EMBEDDING_CACHE_TTL_SECONDS", "86400"))
_redis_state = {"client": None, "down_until": 0.0}


def _redis():
    if os.getenv("SEARCH_EMBEDDING_REDIS_CACHE", "true").strip().lower() not in ("1", "true", "yes"):
        return None
    if os.getenv("REDIS_FALLBACK_MEMORY", "").strip().lower() in ("1", "true", "yes"):
        return None
    if time.monotonic() < _redis_state["down_until"]:
        return None
    if _redis_state["client"] is None:
        try:
            import redis

            from app.core.config import get_settings

            settings = get_settings()
            _redis_state["client"] = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                socket_timeout=0.2,
                socket_connect_timeout=0.2,
            )
        except Exception:
            _redis_state["down_until"] = time.monotonic() + 30
            return None
    return _redis_state["client"]


def cached_embedding(model, text, compute):
    """Embedding of `text` from Redis, else computed and stored. Returns a tuple of floats."""
    key = "search:emb:" + model + ":" + hashlib.sha256(text.encode()).hexdigest()
    client = _redis()
    if client is not None:
        try:
            raw = client.get(key)
            if raw:
                return tuple(np.frombuffer(raw, dtype=np.float32).tolist())
        except Exception:
            _redis_state["down_until"] = time.monotonic() + 30
            client = None
    # Rounded through float32 (what Qdrant stores) so a hit and a miss score identically.
    vector = tuple(np.asarray(compute(), dtype=np.float32).tolist())
    if client is not None:
        try:
            client.set(key, np.asarray(vector, dtype=np.float32).tobytes(), ex=_REDIS_TTL)
        except Exception:
            _redis_state["down_until"] = time.monotonic() + 30
    return vector


class EmbeddingClient:
    def generate_text_embedding(self, text):
        return list(self._embedding(text))

    @lru_cache(maxsize=256)
    def _embedding(self, text):
        # Only deterministic model output is cached, never user-visible results.
        return cached_embedding(
            "clip-vit-b-32",
            text,
            lambda: encode_text([text])[0].detach().cpu().tolist(),
        )


@lru_cache(maxsize=256)
def _passage_query_embedding(text):
    from modules.shared.semantic_index import TEXT_REVISION, encode_passages

    return cached_embedding(
        "minilm-l6-v2-" + TEXT_REVISION[:12], text, lambda: [float(x) for x in encode_passages([text])[0]]
    )


def passage_query_embedding(text):
    """Text-index (MiniLM) embedding of a query, cached like the CLIP one."""
    return list(_passage_query_embedding(text))


@lru_cache
def get_embedding_client():
    return EmbeddingClient()
