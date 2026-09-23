"""Database-free checks for hybrid relevance: similarity cutoff, bounded boosts, stop words."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.repositories.file_repository import conditions
from app.services.ranking_service import RankingService
from app.utils.relevance import within_margin
from app.utils.rrf import FusionResult, RankedItem, reciprocal_rank_fusion


def hits(*scores):
    return [RankedItem(id=f"d{i}", rank=i + 1, raw_score=s) for i, s in enumerate(scores)]


def file(downloads=0, previews=0, age_days=1):
    return SimpleNamespace(
        ingested_at=datetime.now(timezone.utc) - timedelta(days=age_days),
        download_count=downloads,
        file_preview_count=previews,
    )


def test_margin_keeps_only_hits_close_to_the_best():
    kept = within_margin(hits(0.90, 0.85, 0.70, 0.60), 0.08)
    assert [item.id for item in kept] == ["d0", "d1"]


def test_margin_always_keeps_the_best_hit_without_a_reference():
    assert [item.id for item in within_margin(hits(0.30, 0.10), 0.01)] == ["d0"]
    assert within_margin([], 0.08) == []


def test_reference_from_the_whole_catalog_can_empty_a_filtered_result():
    # The filter removed every relevant document: the leftovers must not be promoted.
    assert within_margin(hits(0.65, 0.64), 0.08, reference=0.90) == []


def test_popularity_cannot_outrank_a_clearly_better_match():
    strong = FusionResult(id="strong", rrf_score=0.0164)  # rank 1 in both retrievers
    weak = FusionResult(id="weak", rrf_score=0.0090)  # a single retriever, lower rank
    files = {"strong": file(), "weak": file(downloads=10_000, previews=10_000, age_days=0)}
    ranked = RankingService().rank_and_adjust([weak, strong], files)
    assert [r.id for r in ranked] == ["strong", "weak"]


def test_popularity_breaks_ties_between_equally_relevant_results():
    plain = FusionResult(id="plain", rrf_score=0.0100)
    popular = FusionResult(id="popular", rrf_score=0.0100)
    files = {"plain": file(age_days=400), "popular": file(downloads=40, age_days=400)}
    ranked = RankingService().rank_and_adjust([plain, popular], files)
    assert ranked[0].id == "popular"


def test_boost_is_bounded_and_ignores_unknown_files():
    boosted = FusionResult(id="a", rrf_score=1.0)
    unknown = FusionResult(id="b", rrf_score=1.0)
    RankingService().rank_and_adjust(
        [boosted, unknown], {"a": file(downloads=10**6, previews=10**6, age_days=0)}
    )
    assert 1.0 < boosted.rrf_score <= 1.05
    assert unknown.rrf_score == 1.0


def test_boosts_apply_to_vector_only_results_like_keyword_ones():
    both = FusionResult(id="kw", rrf_score=0.0100, match_sources=["keyword", "vector"])
    vec_only = FusionResult(id="vec", rrf_score=0.0100, match_sources=["vector"])
    files = {"kw": file(age_days=400), "vec": file(age_days=400)}
    ranked = RankingService().rank_and_adjust([both, vec_only], files)
    assert ranked[0].rrf_score == ranked[1].rrf_score  # no branch is favoured


def test_stop_words_do_not_become_search_terms():
    _, tokens, _ = conditions("find images of the ice", None)
    assert "of" not in tokens and "the" not in tokens
    assert "ice" in tokens


def test_a_query_of_only_stop_words_still_searches():
    _, tokens, _ = conditions("of the", None)
    assert tokens == ["of", "the"]


def test_wildcard_query_has_no_terms():
    assert conditions("*", None)[1] == []


def test_fusion_rewards_agreement_between_retrievers():
    fused = reciprocal_rank_fusion(
        keyword_results=[RankedItem(id="both", rank=3, raw_score=1), RankedItem(id="kw", rank=1, raw_score=1)],
        vector_results=[RankedItem(id="both", rank=3, raw_score=1)],
    )
    assert fused[0].id == "both"
