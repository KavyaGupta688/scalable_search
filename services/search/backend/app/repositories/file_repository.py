from sqlalchemy import select, func, or_, update, desc, cast, String, case, text, literal, union_all
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
            select(F, score.label("score"), func.count().over().label("total"))
            .where(*clauses)
            .order_by(desc("score"), F.ingested_at.desc(), F.file_id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()
        total = rows[0][2] if rows else 0
        if not rows and offset:
            total = await self.db.scalar(select(func.count()).select_from(F).where(*clauses))
        return [(row[0], float(row[1])) for row in rows], total or 0

    async def compute_facets(self, query="", filters=None):
        clauses, _, _ = conditions(query, filters)
        # One database round trip, with the same current entitlement predicates
        # applied before every aggregate. No results or permissions are cached.
        eligible = select(F.file_type, F.category, F.dataset_id, F.dataset_name,
                          F.ai_generated, F.pii_detected, F.tags).where(*clauses).cte("facet_files")
        groups = {"file_types": "file_type", "categories": "category",
                  "datasets": "dataset_id", "ai_generated": "ai_generated",
                  "pii_detected": "pii_detected"}
        statements = []
        for name, field in groups.items():
            column = eligible.c[field]
            label = func.min(eligible.c.dataset_name) if name == "datasets" else literal(None, String)
            statements.append(select(literal(name).label("kind"), cast(column, String).label("value"),
                                     func.count().label("count"), label.label("label"))
                              .where(column.isnot(None)).group_by(column)
                              .order_by(func.count().desc(), column).limit(100))
        tags = select(func.json_array_elements_text(eligible.c.tags).label("tag")).subquery()
        statements.append(select(literal("top_tags"), tags.c.tag, func.count(), literal(None, String))
                          .group_by(tags.c.tag).order_by(func.count().desc(), tags.c.tag).limit(15))
        statements.append(select(literal("total"), literal(""), func.count(), literal(None, String))
                          .select_from(eligible))
        result = {name: [] for name in (*groups, "top_tags")}
        total = 0
        for kind, value, count, label in (await self.db.execute(union_all(*statements))).all():
            if kind == "total":
                total = count
            else:
                result[kind].append(FacetCountItem(value=value, count=count, label=label))
        return FacetsResponse(**result, total_matches=total)

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
