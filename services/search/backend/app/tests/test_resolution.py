"""Database-free checks for resolution tiers and word-start keyword matching."""

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.file_repository import conditions, word_start
from app.models.file_metadata import FileMetadata as F
from app.schemas.filters import SearchFilters
from app.utils.resolution import RESOLUTION_IDS, resolution_clause, tier_of


def sql(clause):
    return str(clause.compile(dialect=postgresql.dialect()))


@pytest.mark.parametrize(
    "width,height,tier",
    [
        (3840, 2160, "4k"),  # UHD
        (4096, 2160, "4k"),  # DCI 4K
        (4000, 3000, "4k"),  # 12 MP phone photo
        (2160, 3840, "4k"),  # portrait: the longer edge decides
        (3839, 2160, "2k"),
        (2560, 1440, "2k"),
        (2559, 1440, "fhd"),
        (1920, 1080, "fhd"),
        (1919, 1080, "hd"),
        (1280, 720, "hd"),
        (1279, 720, "sd"),
        (640, 480, "sd"),
        (1, 1, "sd"),
        (1920, None, "fhd"),  # one known side still classifies
        (None, 3840, "4k"),
        (None, None, None),
        (0, 0, None),
    ],
)
def test_tier_boundaries(width, height, tier):
    assert tier_of(width, height) == tier


def test_every_known_size_falls_in_exactly_one_tier():
    ids = [t for t in RESOLUTION_IDS if t != "unknown"]
    for edge in (1, 640, 1279, 1280, 1919, 1920, 2559, 2560, 3839, 3840, 8000):
        assert tier_of(edge, 100) in ids


def test_resolution_filter_compiles_to_a_long_edge_range():
    text = sql(resolution_clause(["fhd"]))
    assert "greatest(" in text.lower()
    assert ">=" in text and "<" in text  # bounded above by the next tier


def test_top_tier_has_no_upper_bound_and_unknown_needs_media_type():
    assert "<" not in sql(resolution_clause(["4k"]))
    unknown = str(resolution_clause(["unknown"]).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "IS NULL" in unknown and "<= 0" in unknown and "file_type IN" in unknown


def test_resolution_filter_is_part_of_the_search_conditions():
    clauses, _, _ = conditions("*", SearchFilters(resolutions=["4k"]))
    assert any("greatest(" in sql(c).lower() for c in clauses)


def test_unknown_tiers_are_rejected_and_ids_normalised():
    with pytest.raises(ValueError):
        SearchFilters(resolutions=["8k"])
    assert SearchFilters(resolutions=["4K", "FHD"]).resolutions == ["4k", "fhd"]
    assert SearchFilters(resolutions=[]).resolutions is None


def test_keyword_match_is_anchored_at_a_word_start():
    rendered = sql(word_start(F.title, "ai"))
    assert "~*" in rendered  # case-insensitive regex, not ILIKE '%ai%'
    assert "ILIKE" not in rendered.upper()


def test_word_start_escapes_regex_metacharacters():
    compiled = word_start(F.title, "c++").compile(dialect=postgresql.dialect())
    assert list(compiled.params.values()) == [r"\yc\+\+"]
