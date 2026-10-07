import re

from sqlalchemy import select, func, or_, and_, update, desc, cast, String, case, text, false, literal_column
from app.models.file_metadata import FileMetadata as F
from app.schemas.filters import FacetsResponse, FacetCountItem
from app.utils.filters import build_sqlalchemy_filters
from app.utils.query_normalizer import extract_significant_tokens, tokenize, term_pattern, term_variants
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


def word_match(field, token):
    """Whole terms with simple plurals: ball matches balls, never balloon."""
    return field.op("~*")(_word_regex(token))


# Set at startup from what the migration has built (see detect_fts):
# "enabled" - file_metadata.search_vector and its trigger (full-text prefilter);
# "trigram" - the pg_trgm index on SEARCH_DOCUMENT_SQL (prefilter for other scripts).
FTS = {"enabled": False, "trigram": False}
_FTS_TOKEN = re.compile(r"[a-z0-9]+")

# Every keyword field joined by spaces, in the order conditions() matches them. The
# migration indexes exactly this expression (scripts/migrate_integration.py); keep the
# two identical or PostgreSQL will not use the index.
SEARCH_DOCUMENT_SQL = (
    "coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || "
    "coalesce(file_name, '') || ' ' || coalesce(category, '') || ' ' || "
    "coalesce(content_summary, '') || ' ' || coalesce(ocr_text, '') || ' ' || "
    "coalesce(transcript, '') || ' ' || coalesce(caption, '') || ' ' || "
    "coalesce(CAST(tags AS VARCHAR), '')"
)
TRIGRAM_INDEX = "file_metadata_search_text_trgm_idx"


def _enabled(name, default="true"):
    import os

    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


async def detect_fts(db):
    """Enable each prefilter only if the migration has built what it needs."""
    if not _enabled("SEARCH_FTS_PREFILTER"):
        FTS.update(enabled=False, trigram=False)
        return False
    found = await db.scalar(
        text(
            "SELECT count(*) FROM pg_trigger WHERE tgname='file_metadata_search_vector_trigger' "
            "AND tgrelid=to_regclass('file_metadata') AND EXISTS (SELECT 1 FROM "
            "information_schema.columns WHERE table_schema=current_schema() "
            "AND table_name='file_metadata' AND column_name='search_vector')"
        )
    )
    trigram = await db.scalar(
        text(
            "SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid "
            "WHERE c.relname=:name AND i.indrelid=to_regclass('file_metadata') AND i.indisvalid"
        ),
        {"name": TRIGRAM_INDEX},
    )
    FTS.update(enabled=bool(found), trigram=bool(trigram))
    return FTS["enabled"]


def _word_regex(token):
    return r"(?<![[:alnum:]])" + term_pattern(token) + r"(?![[:alnum:]])"


def fts_prefilter(tokens, match_all=True):
    """An index-backed condition that keeps every row the regex keyword match keeps.

    Plain ASCII terms use the full-text vector: for them PostgreSQL's parser and the
    regex word boundary provably agree. Other terms (any script) use the trigram index,
    which PostgreSQL applies to the same regex over all keyword fields joined by spaces;
    a whole-term match in any field is a match in the joined text. Rows without a vector
    (too large, or written before the migration) always pass. The regex in conditions()
    still decides the match and _score still ranks, so results and order are unchanged;
    only fewer rows are scanned.
    """
    if not FTS["enabled"] or not tokens:
        return None
    ascii_terms = [token for token in tokens if _FTS_TOKEN.fullmatch(token)]
    other_terms = [token for token in tokens if not _FTS_TOKEN.fullmatch(token)]
    parts = []
    if ascii_terms:
        vector = literal_column("file_metadata.search_vector")
        groups = ["(" + " | ".join(term_variants(token)) + ")" for token in ascii_terms]
        query = func.to_tsquery("simple", (" & " if match_all else " | ").join(groups))
        parts.append(or_(vector.is_(None), vector.op("@@")(query)))
    if other_terms and FTS["trigram"]:
        document = literal_column("(" + SEARCH_DOCUMENT_SQL + ")")
        parts.extend(document.op("~*")(_word_regex(token)) for token in other_terms)
        other_terms = []
    if match_all:
        # Each part is implied by the match, so any subset of them is still a superset.
        return and_(*parts) if parts else None
    # OR mode cannot drop a term without dropping its matches, so it needs every term.
    if not parts or other_terms:
        return None
    return or_(*parts)


def conditions(query, filters, match_all=True):
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
        prefilter = fts_prefilter(tokens, match_all)
        if prefilter is not None:
            clauses.append(prefilter)
        clauses.append((and_ if match_all else or_)(*(or_(*(word_match(field, token) for field in fields)) for token in tokens)))
    elif query.strip().lower() not in ("", "*", "all"):
        clauses.append(false())
    return clauses, tokens, fields


class FileRepository:
    def __init__(self, db, read_db=None):
        # Primary: result rows, visibility checks and writes. Read: ranking and facets,
        # which may come from a replica; callers re-check returned ids on the primary.
        self.db = db
        self.read_db = read_db if read_db is not None else db

    @property
    def has_replica(self):
        return self.read_db is not self.db

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
                case((word_match(field, token), weight), else_=0)
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
        score = self._score(tokens, fields)
        # Only id and size are read: a download plan never loads full rows.
        stmt = (
            select(F.file_id, F.file_size, func.count().over())
            .where(*clauses)
            .order_by(desc(score), F.ingested_at.desc(), F.file_id)
            .limit(limit)
        )
        rows = (await self.read_db.execute(stmt)).all()
        total = rows[0][2] if rows else 0
        return [(row[0], int(row[1])) for row in rows], total

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

    async def search_keyword(self, query, filters=None, limit=50, offset=0, match_all=True):
        clauses, tokens, fields = conditions(query, filters, match_all=match_all)
        score = self._score(tokens, fields)
        stmt = (
            select(F, score.label("score"), func.count().over().label("total"))
            .where(*clauses)
            .order_by(desc("score"), F.ingested_at.desc(), F.file_id)
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.read_db.execute(stmt)).all()
        total = rows[0][2] if rows else 0
        if not rows and offset:
            total = await self.read_db.scalar(select(func.count()).select_from(F).where(*clauses))
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
                await self.read_db.execute(
                    select(*columns)
                    .where(*(clauses if where is None else where))
                    .group_by(column)
                    # Ties ordered by value, so every replica and plan returns the same list.
                    .order_by(func.count().desc(), column)
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
                await self.read_db.execute(
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
                await self.read_db.execute(
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
            await self.read_db.execute(
                select(sub.c.tag, func.count())
                .group_by(sub.c.tag)
                .order_by(func.count().desc(), sub.c.tag)
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
            total_matches=await self.read_db.scalar(
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
