from typing import List, Optional, Dict, Any, Tuple
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, update, desc, text, bindparam
from app.core.config import get_settings
from app.db.postgres import FTS_EXPRESSION_SQL
from app.models.file_metadata import FileMetadata
from app.schemas.filters import SearchFilters, FacetsResponse, FacetCountItem
from app.utils.filters import build_sqlalchemy_filters
from app.utils.query_normalizer import tokenize

logger = logging.getLogger(__name__)
settings = get_settings()

# Safety cap for the SQLite/dev keyword-search path only. Production runs on
# PostgreSQL full-text search (GIN-indexed, scored and paginated in SQL - see
# _search_keyword_postgres below) and never hits this cap. This bound exists
# purely so a large SQLite dev/test database can't exhaust process memory the
# way the previous "load every match, then score in Python" implementation did.
SQLITE_CANDIDATE_SCAN_CAP = 5000


class FileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, file_id: str) -> Optional[FileMetadata]:
        stmt = select(FileMetadata).where(FileMetadata.file_id == file_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(self, file_ids: List[str]) -> List[FileMetadata]:
        if not file_ids:
            return []
        stmt = select(FileMetadata).where(FileMetadata.file_id.in_(file_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_keyword(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Tuple[FileMetadata, float]], int]:
        """
        Full-text/keyword search across title, description, tags, OCR,
        transcript, caption. Scoring, filtering, ordering and pagination all
        happen in SQL (not in Python) so this scales independently of how
        many rows match - critical once the catalog holds millions of files.
        """
        filter_clauses = build_sqlalchemy_filters(filters)

        if query.lower() in ["all", "*", ""]:
            stmt = (
                select(FileMetadata)
                .where(*filter_clauses)
                .order_by(desc(FileMetadata.ingested_at))
                .offset(offset)
                .limit(limit)
            )
            count_stmt = select(func.count()).select_from(FileMetadata).where(*filter_clauses)
            res = await self.db.execute(stmt)
            count_res = await self.db.execute(count_stmt)
            files = list(res.scalars().all())
            total = count_res.scalar() or 0
            return [(f, 1.0) for f in files], total

        if settings.is_postgres:
            return await self._search_keyword_postgres(query, filter_clauses, limit, offset)
        return await self._search_keyword_ilike(query, filter_clauses, limit, offset)

    async def _search_keyword_postgres(
        self,
        query: str,
        filter_clauses: List[Any],
        limit: int,
        offset: int
    ) -> Tuple[List[Tuple[FileMetadata, float]], int]:
        """
        Postgres path: uses websearch_to_tsquery against the weighted
        tsvector expression backed by the GIN index created in
        db/postgres.py::_ensure_search_indexes. The expression here MUST
        match that index's expression exactly for the planner to use it.
        """
        match_clause = text(f"({FTS_EXPRESSION_SQL}) @@ websearch_to_tsquery('english', :fts_query)")
        # TextClause doesn't support .label()/.desc() (SQLAlchemy raises
        # NotImplementedError) - so the alias is written directly in the raw
        # SQL and referenced by name in a raw ORDER BY instead.
        rank_expr = text(f"ts_rank_cd(({FTS_EXPRESSION_SQL}), websearch_to_tsquery('english', :fts_query)) AS fts_rank")

        stmt = (
            select(FileMetadata, rank_expr)
            .where(*filter_clauses, match_clause)
            .order_by(text("fts_rank DESC"))
            .offset(offset)
            .limit(limit)
            .params(fts_query=query)
        )
        count_stmt = (
            select(func.count())
            .select_from(FileMetadata)
            .where(*filter_clauses, match_clause)
            .params(fts_query=query)
        )

        res = await self.db.execute(stmt)
        rows = res.all()
        count_res = await self.db.execute(count_stmt)
        total = count_res.scalar() or 0

        return [(row[0], float(row[1])) for row in rows], total

    async def _search_keyword_ilike(
        self,
        query: str,
        filter_clauses: List[Any],
        limit: int,
        offset: int
    ) -> Tuple[List[Tuple[FileMetadata, float]], int]:
        """
        Dev/SQLite fallback only (no GIN/FTS support). Bounded by
        SQLITE_CANDIDATE_SCAN_CAP so a larger local dataset can't blow up
        process memory; production must run on PostgreSQL (see
        db/postgres.py's production guard) and never reaches this path.
        """
        tokens = tokenize(query)
        if not tokens:
            # Query had no indexable tokens (e.g. pure punctuation) - fall
            # back to filter-only, most-recent-first, no scoring possible.
            stmt = (
                select(FileMetadata)
                .where(*filter_clauses)
                .order_by(desc(FileMetadata.ingested_at))
                .offset(offset)
                .limit(limit)
            )
            count_stmt = select(func.count()).select_from(FileMetadata).where(*filter_clauses)
            res = await self.db.execute(stmt)
            count_res = await self.db.execute(count_stmt)
            files = list(res.scalars().all())
            total = count_res.scalar() or 0
            return [(f, 1.0) for f in files], total

        match_conditions = []
        for token in tokens:
            t_pattern = f"%{token}%"
            match_conditions.append(
                or_(
                    FileMetadata.title.ilike(t_pattern),
                    FileMetadata.description.ilike(t_pattern),
                    FileMetadata.file_name.ilike(t_pattern),
                    FileMetadata.category.ilike(t_pattern),
                    FileMetadata.content_summary.ilike(t_pattern),
                    FileMetadata.ocr_text.ilike(t_pattern),
                    FileMetadata.transcript.ilike(t_pattern),
                    FileMetadata.caption.ilike(t_pattern)
                )
            )
        query_clauses = filter_clauses + [or_(*match_conditions)]

        count_stmt = select(func.count()).select_from(FileMetadata).where(*query_clauses)
        count_res = await self.db.execute(count_stmt)
        total = count_res.scalar() or 0

        candidate_stmt = (
            select(FileMetadata)
            .where(*query_clauses)
            .order_by(desc(FileMetadata.ingested_at))
            .limit(SQLITE_CANDIDATE_SCAN_CAP)
        )
        res = await self.db.execute(candidate_stmt)
        candidates = list(res.scalars().all())
        if total > SQLITE_CANDIDATE_SCAN_CAP:
            logger.warning(
                f"SQLite keyword search matched {total} rows, scoring only the first "
                f"{SQLITE_CANDIDATE_SCAN_CAP} (dev-only path; run on PostgreSQL in production)."
            )

        scored_results: List[Tuple[FileMetadata, float]] = []
        for file in candidates:
            score = 0.0
            t_lower = (file.title or "").lower()
            d_lower = (file.description or "").lower()
            c_lower = (file.caption or "").lower()
            ocr_lower = (file.ocr_text or "").lower()
            tr_lower = (file.transcript or "").lower()
            sum_lower = (file.content_summary or "").lower()
            cat_lower = (file.category or "").lower()

            for token in tokens:
                if token in t_lower:
                    score += 5.0
                if token in cat_lower:
                    score += 4.0
                if token in c_lower:
                    score += 3.0
                if token in sum_lower:
                    score += 2.5
                if token in d_lower:
                    score += 2.0
                if token in ocr_lower:
                    score += 1.5
                if token in tr_lower:
                    score += 1.5
                if file.tags and any(token in str(t).lower() for t in file.tags):
                    score += 3.0

            scored_results.append((file, score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        paginated = scored_results[offset: offset + limit]
        return paginated, total

    async def compute_facets(self, query: str = "", filters: Optional[SearchFilters] = None) -> FacetsResponse:
        """
        Computes facet counts via SQL GROUP BY aggregation - never by loading
        matching rows into Python. This is what keeps the facets panel (shown
        on every search) fast regardless of catalog size.
        """
        filter_clauses = build_sqlalchemy_filters(filters)

        if query and query.lower() not in ["all", "*", ""]:
            if settings.is_postgres:
                filter_clauses.append(
                    text(f"({FTS_EXPRESSION_SQL}) @@ websearch_to_tsquery('english', :facet_fts_query)")
                    .bindparams(facet_fts_query=query)
                )
            else:
                tokens = tokenize(query)
                if tokens:
                    match_conditions = [
                        or_(
                            FileMetadata.title.ilike(f"%{t}%"),
                            FileMetadata.description.ilike(f"%{t}%"),
                            FileMetadata.caption.ilike(f"%{t}%"),
                            FileMetadata.ocr_text.ilike(f"%{t}%"),
                            FileMetadata.transcript.ilike(f"%{t}%")
                        ) for t in tokens
                    ]
                    filter_clauses.append(or_(*match_conditions))

        total_stmt = select(func.count()).select_from(FileMetadata).where(*filter_clauses)
        file_types_stmt = (
            select(FileMetadata.file_type, func.count().label("cnt"))
            .where(*filter_clauses).group_by(FileMetadata.file_type).order_by(desc("cnt"))
        )
        categories_stmt = (
            select(FileMetadata.category, func.count().label("cnt"))
            .where(*filter_clauses).group_by(FileMetadata.category).order_by(desc("cnt"))
        )
        datasets_stmt = (
            select(FileMetadata.dataset_name, func.count().label("cnt"))
            .where(*filter_clauses).group_by(FileMetadata.dataset_name).order_by(desc("cnt"))
        )
        ai_stmt = (
            select(FileMetadata.ai_generated, func.count().label("cnt"))
            .where(*filter_clauses).group_by(FileMetadata.ai_generated)
        )
        pii_stmt = (
            select(FileMetadata.pii_detected, func.count().label("cnt"))
            .where(*filter_clauses).group_by(FileMetadata.pii_detected)
        )

        total = (await self.db.execute(total_stmt)).scalar() or 0
        file_types_rows = (await self.db.execute(file_types_stmt)).all()
        categories_rows = (await self.db.execute(categories_stmt)).all()
        datasets_rows = (await self.db.execute(datasets_stmt)).all()
        ai_rows = (await self.db.execute(ai_stmt)).all()
        pii_rows = (await self.db.execute(pii_stmt)).all()
        top_tags_rows = await self._compute_top_tags(filters, query, limit=15)

        ai_label = {True: "AI-Generated", False: "Human / Authentic", None: "Unknown"}
        pii_label = {True: "PII Detected", False: "No PII (Safe)", None: "Unknown"}

        return FacetsResponse(
            file_types=[FacetCountItem(value=v, count=c) for v, c in file_types_rows],
            categories=[FacetCountItem(value=v, count=c) for v, c in categories_rows],
            datasets=[FacetCountItem(value=v, count=c) for v, c in datasets_rows],
            ai_generated=[FacetCountItem(value=ai_label[v], count=c) for v, c in ai_rows if c > 0],
            pii_detected=[FacetCountItem(value=pii_label[v], count=c) for v, c in pii_rows if c > 0],
            top_tags=[FacetCountItem(value=v, count=c) for v, c in top_tags_rows],
            total_matches=total
        )

    def _build_parameterized_where(self, filters: Optional[SearchFilters], query: str) -> Tuple[str, dict, list]:
        """
        Builds a WHERE fragment for raw SQL using only named bind parameters
        (never string-interpolated values) - safe against SQL injection even
        though filter values (categories, dataset ids, free-text query) come
        from the public search API. Returns (where_sql, params, bindparams)
        where `bindparams` holds the `expanding=True` markers required for
        IN-list parameters to work with SQLAlchemy's text().
        """
        conditions: List[str] = []
        params: dict = {}
        expanding_binds: list = []

        if filters:
            if filters.file_types:
                conditions.append("file_type IN :ft_top_tags")
                params["ft_top_tags"] = [ft.lower() for ft in filters.file_types]
                expanding_binds.append(bindparam("ft_top_tags", expanding=True))
            if filters.categories:
                conditions.append("category IN :cat_top_tags")
                params["cat_top_tags"] = filters.categories
                expanding_binds.append(bindparam("cat_top_tags", expanding=True))
            if filters.dataset_ids:
                conditions.append("dataset_id IN :ds_top_tags")
                params["ds_top_tags"] = filters.dataset_ids
                expanding_binds.append(bindparam("ds_top_tags", expanding=True))
            if filters.ai_generated is not None:
                conditions.append("ai_generated = :ai_top_tags")
                params["ai_top_tags"] = filters.ai_generated
            if filters.pii_detected is not None:
                conditions.append("pii_detected = :pii_top_tags")
                params["pii_top_tags"] = filters.pii_detected
            if filters.date_from:
                conditions.append("ingested_at >= :date_from_top_tags")
                params["date_from_top_tags"] = filters.date_from
            if filters.date_to:
                conditions.append("ingested_at <= :date_to_top_tags")
                params["date_to_top_tags"] = filters.date_to

        if query and query.lower() not in ["all", "*", ""]:
            if settings.is_postgres:
                conditions.append(f"(({FTS_EXPRESSION_SQL}) @@ websearch_to_tsquery('english', :fts_top_tags))")
                params["fts_top_tags"] = query
            else:
                tokens = tokenize(query)
                token_conditions = []
                for idx, token in enumerate(tokens):
                    key = f"tok_top_tags_{idx}"
                    params[key] = f"%{token}%"
                    token_conditions.append(
                        f"(title LIKE :{key} OR description LIKE :{key} OR caption LIKE :{key} "
                        f"OR ocr_text LIKE :{key} OR transcript LIKE :{key})"
                    )
                if token_conditions:
                    conditions.append("(" + " OR ".join(token_conditions) + ")")

        where_sql = " AND ".join(conditions) if conditions else "1=1"
        return where_sql, params, expanding_binds

    async def _compute_top_tags(self, filters: Optional[SearchFilters], query: str, limit: int) -> List[Tuple[str, int]]:
        """
        Aggregates the `tags` JSON array column via the dialect's native
        JSON-unnest function (GROUP BY + COUNT in SQL) instead of loading
        matching rows into Python. All filter/query values are passed as
        bound parameters, never interpolated into the SQL string.
        """
        where_sql, params, expanding_binds = self._build_parameterized_where(filters, query)
        params["lim"] = limit

        try:
            if settings.is_postgres:
                raw_sql = f"""
                    SELECT tag, COUNT(*) AS cnt FROM (
                        SELECT json_array_elements_text(COALESCE(tags, '[]'::json)) AS tag
                        FROM file_metadata
                        WHERE {where_sql}
                    ) t
                    GROUP BY tag ORDER BY cnt DESC LIMIT :lim
                """
            else:
                raw_sql = f"""
                    SELECT tag.value AS tag, COUNT(*) AS cnt
                    FROM file_metadata, json_each(file_metadata.tags) AS tag
                    WHERE {where_sql}
                    GROUP BY tag.value ORDER BY cnt DESC LIMIT :lim
                """
            stmt = text(raw_sql)
            if expanding_binds:
                stmt = stmt.bindparams(*expanding_binds)
            res = await self.db.execute(stmt, params)
            return [(row[0], row[1]) for row in res.all()]
        except Exception as e:
            logger.warning(f"Top-tags facet aggregation failed, returning empty: {e}")
            return []

    async def increment_preview_count(self, file_id: str):
        stmt = update(FileMetadata).where(FileMetadata.file_id == file_id).values(
            file_preview_count=FileMetadata.file_preview_count + 1
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def increment_download_count(self, file_id: str):
        stmt = update(FileMetadata).where(FileMetadata.file_id == file_id).values(
            download_count=FileMetadata.download_count + 1
        )
        await self.db.execute(stmt)
        await self.db.commit()
