"""File-size buckets for the size filter. Sizes use 1 KB = 1024 bytes, as file managers show them.

Every file belongs to exactly one bucket, so the buckets work as counted filter options.
"""

from typing import List, Optional

from sqlalchemy import and_, case, or_

from app.models.file_metadata import FileMetadata as F

KB = 1024
MB = 1024**2
GB = 1024**3

# (id, label, minimum bytes inclusive, maximum bytes exclusive or None), smallest first.
SIZE_BUCKETS = (
    ("lt100k", "Under 100 KB", 0, 100 * KB),
    ("100k-1m", "100 KB – 1 MB", 100 * KB, MB),
    ("1m-10m", "1 – 10 MB", MB, 10 * MB),
    ("10m-100m", "10 – 100 MB", 10 * MB, 100 * MB),
    ("100m-1g", "100 MB – 1 GB", 100 * MB, GB),
    ("gte1g", "1 GB and larger", GB, None),
)
SIZE_BUCKET_IDS = tuple(bucket[0] for bucket in SIZE_BUCKETS)
SIZE_LABELS = {bucket[0]: bucket[1] for bucket in SIZE_BUCKETS}


def bucket_of(size_bytes: Optional[int]) -> Optional[str]:
    if size_bytes is None or size_bytes < 0:
        return None
    for bucket_id, _, minimum, maximum in SIZE_BUCKETS:
        if size_bytes >= minimum and (maximum is None or size_bytes < maximum):
            return bucket_id
    return None


def size_clause(bucket_ids: List[str]):
    """SQL condition matching any of the given bucket ids."""
    conditions = []
    for bucket_id, _, minimum, maximum in SIZE_BUCKETS:
        if bucket_id not in bucket_ids:
            continue
        condition = F.file_size >= minimum
        if maximum is not None:
            condition = and_(condition, F.file_size < maximum)
        conditions.append(condition)
    return or_(*conditions)


def bucket_case():
    """SQL expression that yields the bucket id of each row."""
    return case(
        *((F.file_size < maximum, bucket_id) for bucket_id, _, _, maximum in SIZE_BUCKETS if maximum is not None),
        else_=SIZE_BUCKETS[-1][0],
    )
