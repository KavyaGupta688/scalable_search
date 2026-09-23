"""Resolution tiers for photos and videos, judged by the longer edge in pixels.

The longer edge makes portrait and landscape files fall in the same tier. Every file with
known dimensions belongs to exactly one tier, so the tiers work as counted filter buckets.
"""

from typing import List, Optional

from sqlalchemy import and_, case, func, or_

from app.models.file_metadata import FileMetadata as F

# (id, label, minimum long edge in pixels), highest tier first.
RESOLUTION_TIERS = (
    ("4k", "4K", 3840),
    ("2k", "2K / QHD", 2560),
    ("fhd", "Full HD", 1920),
    ("hd", "HD", 1280),
    ("sd", "Below HD", 1),
)
UNKNOWN = "unknown"  # an image or video whose dimensions were never measured
RESOLUTION_IDS = tuple(tier[0] for tier in RESOLUTION_TIERS) + (UNKNOWN,)
LABELS = {tier[0]: tier[1] for tier in RESOLUTION_TIERS} | {UNKNOWN: "Unknown"}
MEDIA_TYPES = ("image", "video")


def tier_of(width: Optional[int], height: Optional[int]) -> Optional[str]:
    """Tier id for a pixel size, or None when the size is unknown."""
    edge = max(width or 0, height or 0)
    if edge <= 0:
        return None
    for tier_id, _, minimum in RESOLUTION_TIERS:
        if edge >= minimum:
            return tier_id
    return None


def _long_edge():
    # GREATEST ignores NULLs, so a file with only one known side still classifies.
    return func.greatest(F.width, F.height)


def resolution_clause(tiers: List[str]):
    """SQL condition matching any of the given tier ids."""
    edge = _long_edge()
    conditions = []
    for index, (tier_id, _, minimum) in enumerate(RESOLUTION_TIERS):
        if tier_id not in tiers:
            continue
        condition = edge >= minimum
        if index:  # bounded above by the next tier up
            condition = and_(condition, edge < RESOLUTION_TIERS[index - 1][2])
        conditions.append(condition)
    if UNKNOWN in tiers:
        conditions.append(and_(F.file_type.in_(MEDIA_TYPES), edge.is_(None)))
    return or_(*conditions)


def tier_case():
    """SQL expression that yields the tier id of each row."""
    edge = _long_edge()
    return case(
        *((edge >= minimum, tier_id) for tier_id, _, minimum in RESOLUTION_TIERS),
        else_=UNKNOWN,
    )
