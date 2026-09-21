import re

from sqlalchemy import select, func, or_, update, desc, cast, String, case, text
from app.models.file_metadata import FileMetadata as F
from app.schemas.filters import FacetsResponse, FacetCountItem
from app.utils.filters import build_sqlalchemy_filters
from app.utils.query_normalizer import extract_significant_tokens, tokenize
from app.utils.resolution import (
    LABELS,
    MEDIA_TYPES,
    RESOLUTION_IDS,
    tier_case,
)
from app.utils.size_buckets import SIZE_BUCKET_IDS, SIZE_LABELS, bucket_case

# Facets that ignore their own filter, so every option keeps its count once one is picked.
# facet name -> the filter fields it ignores
SELF_IGNORING_FACETS = {
    "file_types": ("file_types",),
    "resolutions": ("resolutions",),
    "sizes": ("size_buckets", "min_size", "max_size"),
}


def word_start(field, token):
    """Case-insensitive match of `token` at the start of a word.

    "ai" must not match "detail" or "email", and "4k" must not match "24k", while
    "satell" still finds "satellite". A substring match (ILIKE '%token%') cannot tell
    these apart, and short terms are common in this catalog ("ai", "3d", "car", "ice").
    """
    return field.op("~*")(r"\y" + re.escape(token))


def conditions(query, filters):
    clauses = build_sqlalchemy_filters(filters)
    if query.strip().lower() in ("", "*", "all"):
        tokens = []
    else:
        # Stop words ("of", "the") substring-match most documents and add no relevance.
        # A query made only of stop words still searches on them.
        tokens = (extract_significant_tokens(query) or tokenize(query))[:32]
    fields = [
        F.title,
        F.description,
        F.file_name,
        F.category,
        F.content_summary,
        F.ocr_text,
        F.transcript,
        F.caption,
        cast(F.tags, String),
    ]
    if tokens:
        clauses.append(
            or_(
                *(
                    word_start(field, token)
                    for token in tokens
                    for field in fields
                )
            )
        )
    return clauses, tokens, fields


class FileRepository:
    def __init__(self, db):
        self.db = db

    async def get_by_id(self, file_id):
        return await self.db.scalar(
            select(F).where(F.file_id == file_id, *build_sqlalchemy_filters(None))
        )

    async def get_by_ids(self, file_ids):
        if not file_ids:
            return []
        return list(
            (
                await self.db.scalars(
                    select(F).where(
                        F.file_id.in_(file_ids), *build_sqlalchemy_filters(None)
                    )
                )
            ).all()
        )

    @staticmethod
    def _score(tokens, fields):
        """Keyword relevance, identical for search results and download planning."""
        weights = [5, 2, 3, 4, 2, 1, 1, 3, 3]
        score = sum(
            (
                case((word_start(field, token), weight), else_=0)
                for token in tokens
                for field, weight in zip(fields, weights)
            ),
            0,
        )
        if not tokens:
            score = case((F.file_id.isnot(None), 1), else_=0)
        return score

    async def ranked_sizes(self, query, filters=None, limit=30000):
        """(file_id, size_bytes) in exactly the order search returns them, plus the match count."""
        clauses, tokens, fields = conditions(query, filters)
        total = await self.db.scalar(select(func.count()).select_from(F).where(*clauses))
        score = self._score(tokens, fields)
        stmt = (
            select(F.file_id, F.file_size)
            .where(*clauses)
            .order_by(desc(score), F.ingested_at.desc(), F.file_id)
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(row[0], int(row[1])) for row in rows], total or 0

    async def sizes_for(self, file_ids):
        """{file_id: size_bytes} for the visible files among file_ids."""
        if not file_ids:
            return {}
        rows = await self.db.execute(
            select(F.file_id, F.file_size).where(
                F.file_id.in_(list(file_ids)), *build_sqlalchemy_filters(None)
            )
        )
        return {row[0]: int(row[1]) for row in rows}

    async def search_keyword(self, query, filters=None, limit=50, offset=0):
        clauses, tokens, fields = conditions(query, filters)
        total = await self.db.scalar(
            select(func.count()).select_from(F).where(*clauses)
        )
        score = self._score(tokens, fields)
        stmt = (
            select(F, score.label("score"))
            .where(*clauses)
            .order_by(desc("score"), F.ingested_at.desc(), F.file_id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(row[0], float(row[1])) for row in rows], total or 0

    async def compute_facets(
        self,
        query="",
        filters=None,
        scope_ids=None,
        relaxed_scope_ids=None,
    ):
        """Facet counts for a query, or for an explicit set of result ids.

        `scope_ids` counts exactly the documents a search returned (hybrid/vector modes,
        whose matches are not derivable from the keyword query). `type_scope_ids` is the
        same set without the file-type filter, so every type keeps its count.
        `relaxed_scope_ids` maps a facet ("file_types", "resolutions", "sizes") to the
        ids of the search with that facet's own filter ignored.
        """
        relaxed_scope_ids = relaxed_scope_ids or {}
        if scope_ids is None:
            clauses, _, _ = conditions(query, filters)

            def without(facet):
                # A facet ignores its own active filter. Otherwise picking "image" would
                # hide every other type and their counts.
                dropped = {f: None for f in SELF_IGNORING_FACETS[facet] if filters and getattr(filters, f) is not None}
                if dropped:
                    return conditions(query, filters.model_copy(update=dropped))[0]
                return clauses

            type_clauses = without("file_types")
            resolution_clauses = without("resolutions")
            size_clauses = without("sizes")
        else:
            visible = build_sqlalchemy_filters(None)
            clauses = [*visible, F.file_id.in_(list(scope_ids))]

            def in_ids(ids):
                return clauses if ids is None else [*visible, F.file_id.in_(list(ids))]

            type_clauses = in_ids(relaxed_scope_ids.get("file_types"))
            resolution_clauses = in_ids(relaxed_scope_ids.get("resolutions"))
            size_clauses = in_ids(relaxed_scope_ids.get("sizes"))

        async def counts(column, labels=None, display_column=None, where=None):
            columns = [column, func.count()]
            if display_column is not None:
                columns.append(func.min(display_column))
            rows = (
                await self.db.execute(
                    select(*columns)
                    .where(*(clauses if where is None else where))
                    .group_by(column)
                    .order_by(func.count().desc())
                    .limit(100)
                )
            ).all()
            return [
                FacetCountItem(value=labels[row[0]] if labels else str(row[0]), count=row[1],
                               label=row[2] if display_column is not None else None)
                for row in rows
                if row[0] is not None
            ]

        async def resolution_counts():
            tier = tier_case()
            rows = (
                await self.db.execute(
                    select(tier, func.count())
                    .where(*resolution_clauses, F.file_type.in_(MEDIA_TYPES))
                    .group_by(tier)
                )
            ).all()
            found = {row[0]: row[1] for row in rows}
            return [  # fixed tier order, highest first
                FacetCountItem(value=tier_id, count=found[tier_id], label=LABELS[tier_id])
                for tier_id in RESOLUTION_IDS
                if found.get(tier_id)
            ]

        async def size_counts():
            bucket = bucket_case()
            rows = (
                await self.db.execute(
                    select(bucket, func.count()).where(*size_clauses).group_by(bucket)
                )
            ).all()
            found = {row[0]: row[1] for row in rows}
            return [  # smallest first
                FacetCountItem(value=bucket_id, count=found[bucket_id], label=SIZE_LABELS[bucket_id])
                for bucket_id in SIZE_BUCKET_IDS
                if found.get(bucket_id)
            ]

        # JSON tag expansion stays in PostgreSQL; no file records are loaded.
        sub = (
            select(func.json_array_elements_text(F.tags).label("tag"))
            .where(*clauses)
            .subquery()
        )
        tag_rows = (
            await self.db.execute(
                select(sub.c.tag, func.count())
                .group_by(sub.c.tag)
                .order_by(func.count().desc())
                .limit(15)
            )
        ).all()
        return FacetsResponse(
            file_types=await counts(F.file_type, where=type_clauses),
            categories=await counts(F.category),
            datasets=await counts(F.dataset_id, display_column=F.dataset_name),
            ai_generated=await counts(F.ai_generated, {True: "true", False: "false"}),
            pii_detected=await counts(F.pii_detected, {True: "true", False: "false"}),
            top_tags=[FacetCountItem(value=t, count=n) for t, n in tag_rows],
            resolutions=await resolution_counts(),
            sizes=await size_counts(),
            total_matches=await self.db.scalar(
                select(func.count()).select_from(F).where(*clauses)
            ),
        )

    async def increment_preview_count(self, file_id):
        await self.db.execute(
            update(F)
            .where(F.file_id == file_id)
            .values(file_preview_count=F.file_preview_count + 1)
        )
        await self.db.commit()

    async def increment_download_count(self, file_id):
        await self.db.execute(
            update(F)
            .where(F.file_id == file_id)
            .values(download_count=F.download_count + 1)
        )
        await self.db.commit()
