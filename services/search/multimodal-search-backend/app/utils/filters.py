from typing import Optional, List, Any
from sqlalchemy import and_, or_
from qdrant_client.http import models as qmodels
from app.models.file_metadata import FileMetadata
from app.schemas.filters import SearchFilters

def build_sqlalchemy_filters(filters: Optional[SearchFilters]) -> List[Any]:
    """
    Builds a list of SQLAlchemy filter clauses from SearchFilters schema.
    """
    clauses = []
    if not filters:
        return clauses

    if filters.file_types:
        clauses.append(FileMetadata.file_type.in_([ft.lower() for ft in filters.file_types]))

    if filters.categories:
        clauses.append(FileMetadata.category.in_(filters.categories))

    if filters.dataset_ids:
        clauses.append(FileMetadata.dataset_id.in_(filters.dataset_ids))

    if filters.ai_generated is not None:
        clauses.append(FileMetadata.ai_generated == filters.ai_generated)

    if filters.pii_detected is not None:
        clauses.append(FileMetadata.pii_detected == filters.pii_detected)

    if filters.date_from:
        clauses.append(FileMetadata.ingested_at >= filters.date_from)

    if filters.date_to:
        clauses.append(FileMetadata.ingested_at <= filters.date_to)

    if filters.min_width:
        clauses.append(FileMetadata.width >= filters.min_width)

    if filters.min_duration:
        clauses.append(FileMetadata.duration >= filters.min_duration)

    if filters.max_duration:
        clauses.append(FileMetadata.duration <= filters.max_duration)

    return clauses

def build_qdrant_filter(filters: Optional[SearchFilters]) -> Optional[qmodels.Filter]:
    """
    Builds Qdrant payload Filter from SearchFilters schema.
    """
    if not filters:
        return None

    must_conditions = []

    if filters.file_types:
        must_conditions.append(
            qmodels.FieldCondition(
                key="file_type",
                match=qmodels.MatchAny(any=[ft.lower() for ft in filters.file_types])
            )
        )

    if filters.categories:
        must_conditions.append(
            qmodels.FieldCondition(
                key="category",
                match=qmodels.MatchAny(any=filters.categories)
            )
        )

    if filters.dataset_ids:
        must_conditions.append(
            qmodels.FieldCondition(
                key="dataset_id",
                match=qmodels.MatchAny(any=filters.dataset_ids)
            )
        )

    if filters.ai_generated is not None:
        must_conditions.append(
            qmodels.FieldCondition(
                key="ai_generated",
                match=qmodels.MatchValue(value=filters.ai_generated)
            )
        )

    if filters.pii_detected is not None:
        must_conditions.append(
            qmodels.FieldCondition(
                key="pii_detected",
                match=qmodels.MatchValue(value=filters.pii_detected)
            )
        )

    if not must_conditions:
        return None

    return qmodels.Filter(must=must_conditions)
