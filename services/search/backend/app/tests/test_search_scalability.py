"""Database-free checks for the scalability changes (docs/SEARCH_SCALABILITY.md)."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import get_settings
from app.repositories import file_repository
from app.services import hybrid_search_service as hybrid
from app.services import search_cache
from app.services.vector_search_service import VectorSearchService
from app.utils.query_normalizer import term_pattern, term_variants
from app.utils.rrf import FusionResult, RankedItem
from qdrant_client.http import models as qmodels

settings = get_settings()


def hit(point_id, score):
    return SimpleNamespace(id=point_id, score=score, payload={"file_id": point_id}, vector={})


# --- S1: licence gate without the 100k limit ----------------------------------------

def _service(monkeypatch, hits):
    from app.clients import embedding_client

    monkeypatch.setattr(embedding_client, "passage_query_embedding", lambda text: [0.1, 0.2])
    q = Mock()
    q.query_points.return_value = SimpleNamespace(points=hits)
    embedder = Mock()
    embedder.generate_text_embedding.return_value = [0.3, 0.4]
    return VectorSearchService(q, embedder), q


def test_exact_gate_sends_the_eligible_ids(monkeypatch):
    service, q = _service(monkeypatch, [hit("a", 0.9)])
    ranked, total = service._retrieve_multimodal("dog", ["a", "b"], 20, 0)
    query_filter = q.query_points.call_args.kwargs["query_filter"]
    assert any(isinstance(c, qmodels.HasIdCondition) for c in query_filter.must)
    assert q.query_points.call_args.kwargs["limit"] == settings.VECTOR_CANDIDATES
    assert [r.id for r in ranked] == ["a"] and total == 1


def test_large_catalogue_uses_payload_filter_and_sql_verification(monkeypatch):
    service, q = _service(monkeypatch, [hit("a", 0.9), hit("revoked", 0.8), hit("b", 0.7)])
    monkeypatch.setattr(VectorSearchService, "_verify_visible", staticmethod(lambda ids, f: {"a", "b"}))
    ranked, total = service._retrieve_multimodal("dog", None, 20, 0)
    kwargs = q.query_points.call_args.kwargs
    assert not any(isinstance(c, qmodels.HasIdCondition) for c in kwargs["query_filter"].must)
    assert kwargs["query_filter"].must_not[0].key == "license_status"
    assert kwargs["limit"] == settings.VECTOR_CANDIDATES * settings.VECTOR_OVERFETCH
    assert kwargs["search_params"].hnsw_ef == 128
    assert {r.id for r in ranked} == {"a", "b"} and total == 2


def test_multimodal_search_no_longer_refuses_large_candidate_sets(monkeypatch):
    service, _ = _service(monkeypatch, [])
    monkeypatch.setattr(service, "_eligible_ids", lambda filters, exclude_id=None: None)
    seen = {}
    monkeypatch.setattr(service, "_retrieve_multimodal",
                        lambda *args, **kwargs: seen.setdefault("eligible", args[1]) or ([], 0))
    assert service._multimodal_search("dog", None, 20, 0) == ([], 0)
    assert seen["eligible"] is None


@pytest.mark.asyncio
async def test_vector_endpoint_payload_path_verifies_hits(monkeypatch):
    q = Mock()
    q.query_points.return_value = SimpleNamespace(points=[hit("a", 0.9), hit("gone", 0.8)])
    q.count.return_value = SimpleNamespace(count=1)
    service = VectorSearchService(q, Mock())
    monkeypatch.setattr(service, "_eligible_ids", lambda filters, exclude_id=None: None)
    monkeypatch.setattr(VectorSearchService, "_verify_visible", staticmethod(lambda ids, f: {"a"}))
    ranked, total = await service.search_by_vector([0.1], limit=5)
    assert [r.id for r in ranked] == ["a"] and total == 1


# --- S2: full-text prefilter is a superset of the regex match ------------------------

def compile_sql(clause):
    compiled = clause.compile(dialect=postgresql.dialect())
    return str(compiled) + " " + " ".join(str(value) for value in compiled.params.values())


def test_prefilter_is_off_until_detected(monkeypatch):
    monkeypatch.setitem(file_repository.FTS, "enabled", False)
    assert file_repository.fts_prefilter(["dog"]) is None


def test_prefilter_uses_the_same_word_forms_as_the_regex(monkeypatch):
    monkeypatch.setitem(file_repository.FTS, "enabled", True)
    sql = compile_sql(file_repository.fts_prefilter(["dogs", "city"]))
    assert "search_vector IS NULL" in sql
    assert "(dog | dogs) & (cities | city | citys)" in sql
    assert " | ".join(term_variants("people")) in compile_sql(file_repository.fts_prefilter(["people"]))


def test_prefilter_skips_terms_the_parser_might_split(monkeypatch):
    monkeypatch.setitem(file_repository.FTS, "enabled", True)
    # AND mode may drop a term (still a superset); OR mode may not.
    assert "東京" not in compile_sql(file_repository.fts_prefilter(["dog", "東京"]))
    assert file_repository.fts_prefilter(["dog", "東京"], match_all=False) is None


@pytest.mark.parametrize("term", ["dog", "dogs", "city", "cities", "glass", "bus", "person",
                                  "men", "4k", "ai", "status", "flies", "keys"])
def test_variants_are_exactly_the_regex_alternatives(term):
    alternatives = set(term_pattern(term)[3:-1].replace("\\", "").split("|"))
    assert alternatives == set(term_variants(term))
    assert all(re.fullmatch(term_pattern(term), v) for v in term_variants(term))


# --- S6: graceful degradation ---------------------------------------------------------

def _hybrid(monkeypatch, vector_error=None):
    monkeypatch.setattr(search_cache, "get", AsyncMock(return_value=(False, None)))
    monkeypatch.setattr(search_cache, "put", AsyncMock())
    monkeypatch.setattr(hybrid, "VECTOR_BREAKER", hybrid.CircuitBreaker(2, 60))
    file = SimpleNamespace(file_id="a", title="Red dog", description=None, caption=None,
                           file_name="a.jpg", content_summary=None, ocr_text=None,
                           transcript=None, category="Animals", tags=[])
    text = Mock()
    text.search = AsyncMock(return_value=([RankedItem(id="a", rank=1, raw_score=5)], 1, {"a": file}))
    text.file_repo.get_by_ids = AsyncMock(return_value=[])
    vector = Mock()
    vector.search_by_query = AsyncMock(side_effect=vector_error, return_value=([], 0))
    return hybrid.HybridSearchService(text, vector)


@pytest.mark.asyncio
async def test_vector_outage_returns_keyword_results_marked_partial(monkeypatch):
    from app.services import relevance_service

    monkeypatch.setattr(relevance_service, "rerank", lambda q, items, files: items)
    service = _hybrid(monkeypatch, vector_error=RuntimeError("qdrant down"))
    fused, files = await service.fuse_candidates("dog")
    assert [r.id for r in fused] == ["a"]
    assert service.degraded_components == ["vector"]
    search_cache.put.assert_not_called()  # partial answers are never cached


@pytest.mark.asyncio
async def test_reranker_outage_falls_back_to_strict_term_matching(monkeypatch):
    from app.services import relevance_service

    def broken(*args):
        raise RuntimeError("model missing")

    monkeypatch.setattr(relevance_service, "rerank", broken)
    service = _hybrid(monkeypatch)
    assert [r.id for r in (await service.fuse_candidates("red dog"))[0]] == ["a"]
    assert service.degraded_components == ["rerank"]
    service = _hybrid(monkeypatch)
    assert (await service.fuse_candidates("blue dog"))[0] == []


def test_circuit_opens_after_repeated_failures():
    breaker = hybrid.CircuitBreaker(2, 60)
    breaker.failure()
    assert breaker.allow()
    breaker.failure()
    assert not breaker.allow()


# --- S4/S8: caches --------------------------------------------------------------------

class FakeRedis:
    def __init__(self):
        self.store, self.ttl = {}, {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ttl[key] = ex

    async def incr(self, key):
        self.store[key] = str(int(self.store.get(key, "0")) + 1)


@pytest.mark.asyncio
async def test_catalogue_change_invalidates_cached_results(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(search_cache, "_client", AsyncMock(return_value=redis))
    monkeypatch.setattr(search_cache, "_ttl", AsyncMock(return_value=60))
    await search_cache.put("facets", ["dog"], {"total": 3})
    assert await search_cache.get("facets", ["dog"]) == (True, {"total": 3})
    await redis.incr(search_cache.CATALOG_VERSION_KEY)  # what the indexer does
    assert await search_cache.get("facets", ["dog"]) == (False, None)


def test_embedding_cache_is_shared_through_redis(monkeypatch):
    from app.clients import embedding_client

    store = {}
    redis = SimpleNamespace(get=store.get, set=lambda key, value, ex=None: store.__setitem__(key, value))
    monkeypatch.setattr(embedding_client, "_redis", lambda: redis)
    compute = Mock(return_value=[0.5, 0.25])
    assert embedding_client.cached_embedding("m", "dog", compute) == (0.5, 0.25)
    assert embedding_client.cached_embedding("m", "dog", compute) == (0.5, 0.25)
    assert compute.call_count == 1


def test_large_filter_sets_skip_repeated_enumeration(monkeypatch):
    from app.services import vector_search_service as vss

    monkeypatch.setattr(vss.settings, "VECTOR_EXACT_GATE_MAX", 2)
    monkeypatch.setattr(vss, "_LARGE_FILTER_SETS", {})
    conn = Mock()
    conn.execute.return_value.scalars.return_value = ["a", "b", "c"]
    engine = Mock()
    engine.connect.return_value.__enter__ = Mock(return_value=conn)
    engine.connect.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr("modules.shared.integration.database_engine", lambda schema: engine)
    service = VectorSearchService(Mock(), Mock())
    assert service._eligible_ids(None) is None
    assert service._eligible_ids(None) is None
    assert conn.execute.call_count == 1  # second call used the memo


# --- Follow-up fixes: expiry-bounded cache, adaptive fetch, shared scores, trigram ------

def _expiry_db(monkeypatch, next_expiry):
    """Stub the next-expiry lookup; returns a list recording each query's `since`."""
    calls = []

    class Conn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def scalar(self, statement, params):
            calls.append(params["since"])
            return next_expiry

    from app.db import postgres

    monkeypatch.setattr(postgres, "engine", SimpleNamespace(connect=lambda: Conn()))
    monkeypatch.setattr(search_cache, "_expiry", {"version": None, "since": None, "at": None, "checked": 0.0})
    return calls


@pytest.mark.asyncio
async def test_cache_entry_never_outlives_the_next_licence_expiry(monkeypatch):
    import time

    redis = FakeRedis()
    monkeypatch.setattr(search_cache, "_client", AsyncMock(return_value=redis))
    calls = _expiry_db(monkeypatch, time.time() + 20.5)
    await search_cache.put("facets", ["dog"], {"total": 3}, since=time.time())
    assert list(redis.ttl.values()) == [20]  # cut from 60 s to the expiry
    await search_cache.put("facets", ["cat"], {"total": 1}, since=time.time())
    assert len(calls) == 1  # the lookup is reused


@pytest.mark.asyncio
async def test_nothing_is_cached_if_a_licence_expired_while_computing(monkeypatch):
    import time

    redis = FakeRedis()
    monkeypatch.setattr(search_cache, "_client", AsyncMock(return_value=redis))
    _expiry_db(monkeypatch, time.time() - 1)  # expired after `since`, before now
    await search_cache.put("facets", ["dog"], {"total": 3}, since=time.time() - 5)
    assert redis.store == {}


@pytest.mark.asyncio
async def test_nothing_is_cached_when_expiry_is_unknown(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(search_cache, "_client", AsyncMock(return_value=redis))
    from app.db import postgres

    def broken():
        raise RuntimeError("db down")

    monkeypatch.setattr(postgres, "engine", SimpleNamespace(connect=broken))
    monkeypatch.setattr(search_cache, "_expiry", {"version": None, "since": None, "at": None, "checked": 0.0})
    await search_cache.put("facets", ["dog"], {"total": 3})
    assert redis.store == {}


def test_adaptive_fetch_continues_until_the_window_is_full(monkeypatch):
    pages = {0: [hit(f"x{i}", 1) for i in range(4)],      # all fail the SQL check
             4: [hit("a", 1), hit("x9", 1), hit("b", 1), hit("c", 1)],
             8: [hit("d", 1)]}
    calls = []

    def search(limit, offset):
        calls.append(offset)
        return pages.get(offset, [])

    monkeypatch.setattr(VectorSearchService, "_verify_visible",
                        staticmethod(lambda ids, f: {"a", "b", "c", "d"}))
    service = VectorSearchService(Mock(), Mock())
    kept = service._fetch_verified(search, 4, 4, None, lambda h: h.id)
    assert [h.id for h in kept] == ["a", "b", "c", "d"] and calls == [0, 4, 8]
    calls.clear()
    pages[0] = [hit(i, 1) for i in "abcd"]
    service._fetch_verified(search, 4, 4, None, lambda h: h.id)
    assert calls == [0]  # a full first batch costs one round, as before


@pytest.mark.asyncio
async def test_vector_total_is_counted_exactly_on_the_payload_path(monkeypatch):
    q = Mock()
    q.query_points.return_value = SimpleNamespace(points=[hit("a", 0.9)])
    q.count.return_value = SimpleNamespace(count=1234567)
    service = VectorSearchService(q, Mock())
    monkeypatch.setattr(service, "_eligible_ids", lambda filters, exclude_id=None: None)
    monkeypatch.setattr(VectorSearchService, "_verify_visible", staticmethod(lambda ids, f: {"a"}))
    _, total = await service.search_by_vector([0.1], limit=5)
    assert total == 1234567
    assert q.count.call_args.kwargs["exact"] is True


def test_relevance_scores_are_shared_between_replicas(monkeypatch):
    from app.clients import embedding_client
    from app.services import relevance_service as rel

    store = {}
    redis = SimpleNamespace(
        mget=lambda keys: [store.get(k) for k in keys],
        pipeline=lambda transaction=False: SimpleNamespace(
            set=lambda k, v, ex=None: store.__setitem__(k, v.encode()), execute=lambda: None),
    )
    monkeypatch.setattr(embedding_client, "_redis", lambda: redis)
    pair = ("dog", "A dog on grass")
    rel._store_shared({pair: -1.2345678901234567})
    assert rel._shared_scores([pair, ("dog", "other")]) == {pair: -1.2345678901234567}


def test_trigram_prefilter_covers_other_scripts(monkeypatch):
    monkeypatch.setitem(file_repository.FTS, "enabled", True)
    monkeypatch.setitem(file_repository.FTS, "trigram", True)
    sql = compile_sql(file_repository.fts_prefilter(["dog", "東京"]))
    assert "search_vector @@" in sql and "coalesce(title, '')" in sql and "東京" in sql
    # OR mode can now prefilter mixed queries too.
    assert file_repository.fts_prefilter(["dog", "東京"], match_all=False) is not None
    monkeypatch.setitem(file_repository.FTS, "trigram", False)
    assert file_repository.fts_prefilter(["dog", "東京"], match_all=False) is None


def test_trigram_expression_matches_the_migration():
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[5] / "scripts/migrate_integration.py").read_text(encoding="utf-8")
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and node.targets[0].id == "SEARCH_DOCUMENT_SQL":
            assert ast.literal_eval(node.value) == file_repository.SEARCH_DOCUMENT_SQL
            return
    raise AssertionError("migration no longer defines SEARCH_DOCUMENT_SQL")
