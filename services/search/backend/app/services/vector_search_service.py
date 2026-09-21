from typing import List, Optional, Tuple, Dict, Any
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.clients.embedding_client import EmbeddingClient
from app.db.qdrant import get_qdrant_client
from app.core.config import get_settings
from app.schemas.filters import SearchFilters
from app.utils.filters import build_qdrant_filter
from app.utils.relevance import within_margin
from app.utils.rrf import RankedItem

logger = logging.getLogger(__name__)
settings = get_settings()


class VectorSearchService:
    def __init__(self, qdrant_client: QdrantClient, embedding_client: EmbeddingClient):
        self.qdrant = qdrant_client
        self.embedder = embedding_client
        self.collection_name = settings.QDRANT_COLLECTION_NAME

    async def search_by_query(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[RankedItem], int]:
        """
        Generates the query embedding and returns the relevant filtered hits.

        Only hits within VECTOR_SCORE_MARGIN of the best one count, out of a bounded
        window of nearest neighbours. The window is independent of the requested page,
        so the cutoff and the returned total are stable across pages. The total is the
        number of relevant hits, not the number of documents that pass the filters.
        """
        from starlette.concurrency import run_in_threadpool

        query_vector = await run_in_threadpool(
            self.embedder.generate_text_embedding, query
        )
        window = max(settings.VECTOR_CANDIDATES, limit + offset)
        nearest, _ = await self.search_by_vector(
            query_vector, filters=filters, limit=window, offset=0
        )
        reference = None
        if nearest and self._narrows(filters):
            # Relevance is judged against the best match in the whole catalog, not the
            # best of what the filters left.
            reference = max(nearest[0].raw_score, await self._best_score(query_vector))
        relevant = within_margin(nearest, settings.VECTOR_SCORE_MARGIN, reference)
        return relevant[offset : offset + limit], len(relevant)

    @staticmethod
    def _narrows(filters: Optional[SearchFilters]) -> bool:
        return bool(filters) and any(
            value not in (None, [], "") for value in filters.model_dump().values()
        )

    async def _best_score(self, vector: List[float]) -> float:
        """Best similarity for the vector among all published, unexpired documents."""
        from starlette.concurrency import run_in_threadpool

        def query():
            response = self.qdrant.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=build_qdrant_filter(None),
                limit=1,
            )
            points = response.points if hasattr(response, "points") else response
            return float(points[0].score) if points else float("-inf")

        return await run_in_threadpool(query)

    async def search_by_vector(
        self,
        vector: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 50,
        offset: int = 0,
        exclude_id: Optional[str] = None,
    ) -> Tuple[List[RankedItem], int]:
        """
        Searches Qdrant with an explicit vector embedding and filters.
        """
        from starlette.concurrency import run_in_threadpool
        from sqlalchemy import select
        from modules.shared.integration import database_engine
        from app.models.file_metadata import FileMetadata
        from app.utils.filters import build_sqlalchemy_filters

        def allowed_ids():
            with database_engine("search").connect() as conn:
                stmt = select(FileMetadata.file_id).where(
                    *build_sqlalchemy_filters(filters)
                )
                if exclude_id:
                    stmt = stmt.where(FileMetadata.file_id != exclude_id)
                ids = list(conn.execute(stmt.limit(100001)).scalars())
                if len(ids) > 100000:
                    from fastapi import HTTPException

                    raise HTTPException(
                        422, "Narrow the search filters; candidate limit exceeded"
                    )
                return ids

        eligible = await run_in_threadpool(allowed_ids)
        if not eligible:
            return [], 0
        qdrant_filter = build_qdrant_filter(filters)
        qdrant_filter.must.append(qmodels.HasIdCondition(has_id=eligible))

        # If exclude_id is provided, exclude matching file_id in payload
        if exclude_id:
            must_not = [
                qmodels.FieldCondition(
                    key="file_id", match=qmodels.MatchValue(value=exclude_id)
                )
            ]
            if qdrant_filter:
                qdrant_filter.must_not = (qdrant_filter.must_not or []) + must_not
            else:
                qdrant_filter = qmodels.Filter(must_not=must_not)

        try:
            # Check if query_points is supported (qdrant-client >= 1.10)
            if hasattr(self.qdrant, "query_points"):
                response = self.qdrant.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    query_filter=qdrant_filter,
                    limit=limit + offset,
                    with_payload=True,
                )
                search_result = (
                    response.points if hasattr(response, "points") else response
                )
            else:
                search_result = self.qdrant.search(
                    collection_name=self.collection_name,
                    query_vector=vector,
                    query_filter=qdrant_filter,
                    limit=limit + offset,
                    with_payload=True,
                )

            # Apply offset
            sliced_results = search_result[offset : offset + limit]
            ranked_items: List[RankedItem] = []

            for rank_idx, hit in enumerate(sliced_results, start=1):
                payload = getattr(hit, "payload", {}) or {}
                file_id = (
                    payload.get("file_id") if payload else str(getattr(hit, "id", ""))
                )
                score = float(getattr(hit, "score", 0.0))
                ranked_items.append(
                    RankedItem(
                        id=file_id, rank=rank_idx, raw_score=score, metadata=payload
                    )
                )

            total_hits = len(eligible)
            return ranked_items, total_hits

        except Exception as e:
            logger.error(f"Error querying Qdrant: {e}", exc_info=True)
            from fastapi import HTTPException

            raise HTTPException(503, "Vector search is unavailable") from e
