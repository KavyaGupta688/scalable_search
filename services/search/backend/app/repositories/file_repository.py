from sqlalchemy import select, func, or_, update, desc, cast, String, case, text
from app.models.file_metadata import FileMetadata as F
from app.schemas.filters import FacetsResponse, FacetCountItem
from app.utils.filters import build_sqlalchemy_filters
from app.utils.query_normalizer import tokenize


def conditions(query, filters):
    clauses = build_sqlalchemy_filters(filters)
    tokens = [] if query.strip().lower() in ("", "*", "all") else tokenize(query)[:32]
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
                    field.ilike("%" + token + "%")
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

    async def search_keyword(self, query, filters=None, limit=50, offset=0):
        clauses, tokens, fields = conditions(query, filters)
        total = await self.db.scalar(
            select(func.count()).select_from(F).where(*clauses)
        )
        weights = [5, 2, 3, 4, 2, 1, 1, 3, 3]
        score = sum(
            (
                case((field.ilike("%" + token + "%"), weight), else_=0)
                for token in tokens
                for field, weight in zip(fields, weights)
            ),
            0,
        )
        if not tokens:
            score = case((F.file_id.isnot(None), 1), else_=0)
        stmt = (
            select(F, score.label("score"))
            .where(*clauses)
            .order_by(desc("score"), F.ingested_at.desc(), F.file_id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(row[0], float(row[1])) for row in rows], total or 0

    async def compute_facets(self, query="", filters=None):
        clauses, _, _ = conditions(query, filters)

        async def counts(column, labels=None, display_column=None):
            columns = [column, func.count()]
            if display_column is not None:
                columns.append(func.min(display_column))
            rows = (
                await self.db.execute(
                    select(*columns)
                    .where(*clauses)
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
            file_types=await counts(F.file_type),
            categories=await counts(F.category),
            datasets=await counts(F.dataset_id, display_column=F.dataset_name),
            ai_generated=await counts(F.ai_generated, {True: "true", False: "false"}),
            pii_detected=await counts(F.pii_detected, {True: "true", False: "false"}),
            top_tags=[FacetCountItem(value=t, count=n) for t, n in tag_rows],
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
