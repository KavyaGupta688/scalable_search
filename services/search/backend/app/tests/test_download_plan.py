"""Database-free checks for the download plan and the size buckets."""

import pytest
from sqlalchemy.dialects import postgresql

from app.schemas.filters import SearchFilters
from app.utils.download_plan import build_plan
from app.utils.size_buckets import GB, KB, MB, SIZE_BUCKET_IDS, bucket_of, size_clause

MiB = 1024**2
LIMITS = {"max_file_bytes": 128 * MiB, "part_bytes": 100 * MiB, "max_files": 5, "max_total_bytes": 300 * MiB}


def ranked(*sizes_mib):
    return [(f"f{i}", size * MiB) for i, size in enumerate(sizes_mib)]


def plan(sizes_mib, count, **extra):
    return build_plan(ranked(*sizes_mib), total_matches=len(sizes_mib), count=count, limits=LIMITS, **extra)


def test_takes_the_top_n_in_result_order_and_sums_their_sizes():
    result = plan([10, 20, 30, 40], 3, include_ids=True)
    assert result["file_ids"] == ["f0", "f1", "f2"]
    assert result["count"] == 3 and result["total_bytes"] == 60 * MiB
    assert result["within_limits"] is True


def test_ids_are_only_returned_when_asked_for():
    assert "file_ids" not in plan([10, 20], 2)


def test_asking_for_more_than_exists_returns_everything_available():
    result = plan([10, 20], 50)
    assert result["count"] == 2 and result["available"] == 2 and result["requested"] == 50


def test_no_count_means_everything_available():
    assert plan([10, 20, 30], None)["count"] == 3


def test_zero_or_negative_count_selects_nothing():
    for count in (0, -4):
        result = plan([10, 20], count)
        assert result["count"] == 0 and result["within_limits"] is False


def test_files_over_the_per_file_limit_are_left_out_and_counted():
    result = plan([10, 500, 20, 900, 30], 3, include_ids=True)
    assert result["file_ids"] == ["f0", "f2", "f4"]  # 500 MiB and 900 MiB skipped
    assert result["excluded_oversized"] == 2
    assert result["available"] == 3


def test_oversized_files_below_the_selection_are_not_counted_as_skipped():
    result = plan([10, 20, 500], 2)
    assert result["count"] == 2 and result["excluded_oversized"] == 0


def test_over_the_total_limit_reports_how_many_fit():
    result = plan([100, 100, 100, 100], 4)  # 400 MiB against a 300 MiB ceiling
    assert result["within_limits"] is False
    assert result["total_bytes"] == 400 * MiB
    assert result["fit_count"] == 3


def test_over_the_file_count_limit_reports_how_many_fit():
    result = plan([1] * 8, 8)  # ceiling is 5 files
    assert result["within_limits"] is False and result["fit_count"] == 5


def test_fit_count_is_a_leading_prefix_not_a_subset():
    # Skipping the big file to squeeze in later small ones would reorder the results.
    result = plan([120, 120, 100, 5], 4)
    # 120 + 120 = 240 fits, adding 100 exceeds 300. The trailing 5 MiB file would fit on its
    # own, but taking it would change which files are "the top N".
    assert result["fit_count"] == 2


def test_parts_are_packed_in_order():
    result = plan([40, 40, 40, 40, 40], 5)  # 100 MiB parts hold two 40 MiB files each
    assert result["estimated_parts"] == 3
    assert plan([60, 60, 60], 3)["estimated_parts"] == 3  # 60 + 60 does not fit in one part


def test_one_part_when_everything_fits_in_it():
    assert plan([10, 20, 30], 3)["estimated_parts"] == 1
    assert plan([], 3)["estimated_parts"] == 0


def test_truncated_scan_is_flagged():
    result = build_plan(ranked(1, 2), total_matches=13204, count=2, limits=LIMITS)
    assert result["truncated"] is True and result["total_matches"] == 13204


def test_limits_are_echoed_for_the_client():
    assert plan([1], 1)["limits"] == LIMITS


@pytest.mark.parametrize(
    "size,bucket",
    [
        (0, "lt100k"),
        (100 * KB - 1, "lt100k"),
        (100 * KB, "100k-1m"),
        (MB - 1, "100k-1m"),
        (MB, "1m-10m"),
        (10 * MB, "10m-100m"),
        (100 * MB, "100m-1g"),
        (GB - 1, "100m-1g"),
        (GB, "gte1g"),
        (50 * GB, "gte1g"),
        (None, None),
        (-1, None),
    ],
)
def test_size_bucket_boundaries(size, bucket):
    assert bucket_of(size) == bucket


def test_size_filter_validation():
    assert SearchFilters(size_buckets=["1M-10M"]).size_buckets == ["1m-10m"]
    with pytest.raises(ValueError):
        SearchFilters(size_buckets=["huge"])
    with pytest.raises(ValueError):
        SearchFilters(min_size=10, max_size=5)
    assert SearchFilters(min_size=5, max_size=5).min_size == 5
    assert set(SIZE_BUCKET_IDS) == {"lt100k", "100k-1m", "1m-10m", "10m-100m", "100m-1g", "gte1g"}


def test_size_clause_is_bounded_except_for_the_top_bucket():
    bounded = str(size_clause(["1m-10m"]).compile(dialect=postgresql.dialect()))
    assert ">=" in bounded and "<" in bounded
    assert "<" not in str(size_clause(["gte1g"]).compile(dialect=postgresql.dialect()))


def test_everything_oversized_is_distinguishable_from_no_results():
    result = plan([500, 900], None)
    assert result["count"] == 0 and result["available"] == 0
    assert result["oversized_in_scan"] == 2 and result["excluded_oversized"] == 0
    assert plan([], None)["oversized_in_scan"] == 0

