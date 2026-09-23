"""Plans a "download the top N results" request: which files, how big, and whether it fits.

Pure logic, independent of the database, so the size estimate a user sees is exactly what the
download service will accept. Inputs are the search's own ranking order, so "top N" is the N
files at the top of the results list.
"""

from typing import Dict, List, Optional, Sequence, Tuple


def _part_count(sizes: Sequence[int], part_bytes: int) -> int:
    """Archive parts needed when files are packed in order, a new part starting when one is full."""
    parts, used = 0, 0
    for size in sizes:
        if parts == 0 or used + size > part_bytes:
            parts += 1
            used = 0
        used += size
    return parts


def build_plan(
    ranked: Sequence[Tuple[str, int]],
    *,
    total_matches: int,
    count: Optional[int],
    limits: Dict[str, int],
    include_ids: bool = False,
) -> dict:
    """
    ranked: (file_id, size_bytes) in result order; may be shorter than total_matches.
    count: how many files the user wants, or None for as many as possible.
    limits: max_file_bytes, part_bytes, max_files, max_total_bytes.
    """
    max_file = limits["max_file_bytes"]
    max_files = limits["max_files"]
    max_total = limits["max_total_bytes"]
    part_bytes = limits["part_bytes"]

    eligible: List[Tuple[str, int]] = []
    oversized_positions: List[int] = []  # index in `eligible` before which each oversized file sat
    for file_id, size in ranked:
        if size > max_file:
            oversized_positions.append(len(eligible))
        else:
            eligible.append((file_id, size))

    wanted = len(eligible) if count is None else max(0, count)
    selected = eligible[: min(wanted, len(eligible))]
    sizes = [size for _, size in selected]
    total_bytes = sum(sizes)

    # Largest leading selection that satisfies both ceilings.
    fit_count, running = 0, 0
    for _, size in eligible[:max_files]:
        if running + size > max_total:
            break
        running += size
        fit_count += 1

    within_limits = 0 < len(selected) <= max_files and total_bytes <= max_total
    plan = {
        "total_matches": total_matches,
        "requested": count,
        "count": len(selected),
        "available": len(eligible),
        "total_bytes": total_bytes,
        "size_basis": "source",
        "estimated_parts": _part_count(sizes, part_bytes),
        # Oversized files that sat above the last selected file, i.e. were skipped over.
        "excluded_oversized": sum(1 for position in oversized_positions if position < len(selected)),
        # All oversized files in the scanned results, selected or not.
        "oversized_in_scan": len(oversized_positions),
        "within_limits": within_limits,
        "fit_count": fit_count,
        # The scan window can be shorter than the result set; then `available` is a lower bound.
        "truncated": total_matches > len(ranked),
        "limits": dict(limits),
    }
    if include_ids:
        plan["file_ids"] = [file_id for file_id, _ in selected]
    return plan
