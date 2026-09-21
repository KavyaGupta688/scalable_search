from typing import List, Optional

from app.utils.rrf import RankedItem


def within_margin(
    items: List[RankedItem], margin: float, reference: Optional[float] = None
) -> List[RankedItem]:
    """Keeps items scoring within `margin` of the reference score. `items` are best-first.

    The reference defaults to the best item, which is then always kept, so a query with
    any eligible document never comes back empty. Pass the best score of the unfiltered
    catalog as `reference` when filters are active: a filter that excludes every relevant
    document must yield no results instead of promoting the least-bad irrelevant ones.
    """
    if not items:
        return []
    floor = (items[0].raw_score if reference is None else reference) - margin
    return [item for item in items if item.raw_score >= floor]
