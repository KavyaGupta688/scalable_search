from typing import Tuple, List, TypeVar

T = TypeVar("T")

def apply_pagination(items: List[T], limit: int, offset: int) -> Tuple[List[T], int]:
    total = len(items)
    if offset >= total:
        return [], total
    end = min(offset + limit, total)
    return items[offset:end], total
