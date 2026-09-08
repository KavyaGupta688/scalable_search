from typing import List, Optional, Tuple, Dict, Any
import asyncio
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.clients.embedding_client import EmbeddingClient
from app.db.qdrant import get_qdrant_client
from app.core.config import get_settings
from app.schemas.filters import SearchFilters
from app.utils.filters import build_qdrant_filter
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
        offset: int = 0
    ) -> Tuple[List[RankedItem], int]:
        """
        Generates query embedding and searches Qdrant vector index with filters.
        """
        query_vector = self.embedder.generate_text_embedding(query)
        return await self.search_by_vector(query_vector, filters=filters, limit=limit, offset=offset)

    async def search_by_vector(
        self,
        vector: List[float],
        filters: Optional[SearchFilters] = None,
        limit: int = 50,
        offset: int = 0,
        exclude_id: Optional[str] = None
    ) -> Tuple[List[RankedItem], int]:
        """
        Searches Qdrant with an explicit vector embedding and filters.
        """
        qdrant_filter = build_qdrant_filter(filters)
        
        # If exclude_id is provided, exclude matching file_id in payload
        if exclude_id:
            must_not = [qmodels.FieldCondition(key="file_id", match=qmodels.MatchValue(value=exclude_id))]
            if qdrant_filter:
                qdrant_filter.must_not = (qdrant_filter.must_not or []) + must_not
            else:
                qdrant_filter = qmodels.Filter(must_not=must_not)

        search_params = qmodels.SearchParams(hnsw_ef=settings.QDRANT_HNSW_EF_SEARCH)

        try:
            # QdrantClient is a synchronous/blocking client. Run it in a
            # worker thread so a slow Qdrant round-trip does not stall the
            # asyncio event loop - with 3,000+ concurrent users, a blocking
            # call here would serialize every other in-flight request.
            search_result = await asyncio.to_thread(self._run_vector_query, vector, qdrant_filter, limit, offset, search_params)

            ranked_items: List[RankedItem] = []

            for rank_idx, hit in enumerate(search_result, start=1):
                payload = getattr(hit, "payload", {}) or {}
                file_id = payload.get("file_id") if payload else str(getattr(hit, "id", ""))
                score = float(getattr(hit, "score", 0.0))
                ranked_items.append(
                    RankedItem(
                        id=file_id,
                        rank=rank_idx,
                        raw_score=score,
                        metadata=payload
                    )
                )

            total_hits = await self._count_matches(qdrant_filter, fallback=len(ranked_items) + offset)
            return ranked_items, total_hits

        except Exception as e:
            logger.error(f"Error querying Qdrant: {e}", exc_info=True)
            return [], 0

    def _run_vector_query(
        self,
        vector: List[float],
        qdrant_filter: Optional[qmodels.Filter],
        limit: int,
        offset: int,
        search_params: qmodels.SearchParams
    ):
        # Check if query_points is supported (qdrant-client >= 1.10)
        if hasattr(self.qdrant, "query_points"):
            response = self.qdrant.query_points(
                collection_name=self.collection_name,
                query=vector,
                query_filter=qdrant_filter,
                limit=limit,
                offset=offset,
                search_params=search_params,
                with_payload=True
            )
            return response.points if hasattr(response, "points") else response

        return self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=vector,
            query_filter=qdrant_filter,
            limit=limit,
            offset=offset,
            search_params=search_params,
            with_payload=True
        )

    async def _count_matches(self, qdrant_filter: Optional[qmodels.Filter], fallback: int) -> int:
        """
        Returns the number of points matching the filter (not vector
        similarity, which has no well-defined "total"). Uses Qdrant's
        approximate count so this stays cheap at 10M+ point scale rather
        than forcing a full index scan for an exact number.
        """
        try:
            result = await asyncio.to_thread(
                self.qdrant.count,
                collection_name=self.collection_name,
                count_filter=qdrant_filter,
                exact=False
            )
            return int(getattr(result, "count", fallback))
        except Exception as e:
            logger.warning(f"Qdrant count() failed, falling back to page-based estimate: {e}")
            return fallback
