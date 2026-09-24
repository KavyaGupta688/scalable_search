from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from modules.shared import semantic_index as index
from app.services import relevance_service as relevance
from app.utils.rrf import RankedItem, FusionResult, reciprocal_rank_fusion


class Tokenizer:
    def encode(self, text, **kwargs):
        return text.split()
    def decode(self, tokens, **kwargs):
        return " ".join(tokens)


def test_content_passages_ignore_tags_and_preserve_late_text(monkeypatch):
    monkeypatch.setattr(index, "text_bundle", lambda: (Tokenizer(), None))
    chunks = index.text_passages({"title": "Report", "native_document_text": "intro "*1000 + "critical finding", "generated_tags": ["spurious"]})
    assert any("critical finding" in text for text in chunks)
    assert all("spurious" not in text for text in chunks)
    assert all(len(text.split()) <= 220 for text in chunks)


def test_long_file_sampling_keeps_end_and_is_bounded(monkeypatch):
    monkeypatch.setattr(index, "text_bundle", lambda: (Tokenizer(), None))
    chunks = index.text_passages({"native_document_text": " ".join(str(i) for i in range(30000))})
    assert len(chunks) == 64
    assert "29999" in chunks[-1]


def test_fusion_preserves_separate_modalities():
    r = RankedItem(id="a", rank=1, raw_score=.03, metadata={"text_similarity": .6, "visual_similarity": .31, "matched_passage": "A dog"})
    fused = reciprocal_rank_fusion([], [r])[0]
    assert fused.visual_similarity == .31
    assert fused.semantic_similarity == fused.vector_similarity == .6
    assert fused.matched_passage == "A dog"


def test_strong_visual_evidence_survives_text_verifier(monkeypatch):
    file = SimpleNamespace(title="Uninformative caption")
    monkeypatch.setattr(relevance, "_scores", {("dog", text): -9 for text in relevance.passages("dog", file)})
    visual = FusionResult(id="a", rrf_score=.02, visual_similarity=.35)
    assert relevance.rerank("dog", [visual], {"a": file}) == [visual]
    weak = FusionResult(id="a", rrf_score=.02, visual_similarity=.1, semantic_similarity=.1)
    assert relevance.rerank("dog", [weak], {"a": file}) == []


def test_retrieval_never_queries_without_authorized_ids():
    from app.services.vector_search_service import VectorSearchService
    q = Mock()
    assert VectorSearchService(q, Mock())._retrieve_multimodal("dog", [], 20, 0) == ([], 0)
    q.query_points.assert_not_called()


def test_new_index_does_not_replace_legacy_collection(monkeypatch):
    monkeypatch.delenv("SEMANTIC_COLLECTION", raising=False)
    monkeypatch.setenv("QDRANT_COLLECTION_NAME", "legacy")
    assert index.collection_name() == "legacy_v2"


def test_request_dependency_does_not_probe_qdrant(monkeypatch):
    from app.db import qdrant
    expected = object()
    monkeypatch.setattr(qdrant, "client", lambda: expected)
    monkeypatch.setattr(qdrant, "provision", lambda: pytest.fail("Request-time schema probe"))
    assert qdrant.get_qdrant_client() is expected
