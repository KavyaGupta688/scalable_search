from typing import List, Optional, Tuple, Dict, Any
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
        offset: int = 0,
    ) -> Tuple[List[RankedItem], int]:
        """
        Generates the query embedding and returns the relevant filtered hits.

        Retrieves a stable bounded window. The caller verifies query/document relevance
        after hydration, before computing totals, facets, or download selection.
        """
        from starlette.concurrency import run_in_threadpool

        from app.utils.query_normalizer import search_intent, tokenize
        positive, _ = search_intent(query)
        if not tokenize(positive):
            return [], 0
        if settings.USE_MULTIMODAL_INDEX:
            return await run_in_threadpool(self._multimodal_search, positive, filters, limit, offset)
        query_vector = await run_in_threadpool(self.embedder.generate_text_embedding, positive)
        return await self.search_by_vector(query_vector, filters=filters, limit=limit, offset=offset)

    def _multimodal_search(self, query, filters, limit, offset, source_id=None):
        from modules.shared.semantic_index import collection_name, encode_passages, VERSION
        from modules.shared.integration import database_engine
        from app.models.file_metadata import FileMetadata
        from app.utils.filters import build_sqlalchemy_filters
        from sqlalchemy import select
        from fastapi import HTTPException
        # Canonical SQL remains authoritative for entitlement and every user filter.
        with database_engine("search").connect() as conn:
            eligible = list(conn.execute(select(FileMetadata.file_id).where(*build_sqlalchemy_filters(filters)).limit(100001)).scalars())
        eligible = [file_id for file_id in eligible if file_id != source_id]
        if len(eligible) > 100000:
            raise HTTPException(422, "Narrow the search filters; candidate limit exceeded")
        if not eligible:
            return [], 0
        return self._retrieve_multimodal(query, eligible, limit, offset, source_id)

    def _retrieve_multimodal(self, query, eligible, limit, offset, source_id=None):
        """Retrieve only caller-authorized IDs; also usable for offline quality evaluation."""
        from modules.shared.semantic_index import collection_name, encode_passages, VERSION
        from fastapi import HTTPException
        if not eligible:
            return [], 0
        allowed = qmodels.Filter(must=[qmodels.HasIdCondition(has_id=eligible),
            qmodels.FieldCondition(key="representation_version", match=qmodels.MatchValue(value=VERSION))])
        window = max(settings.VECTOR_CANDIDATES, limit + offset)
        queries = None
        if source_id:
            points = self.qdrant.retrieve(collection_name(), ids=[source_id], with_vectors=True)
            if points:
                vectors = points[0].vector
                name = "visual" if vectors.get("visual") else "text"
                if vectors.get(name):
                    queries = [(name, vectors[name][0])]
        if queries is None:
            queries = [("text", encode_passages([query])[0]),
                       ("visual", self.embedder.generate_text_embedding(query))]
        candidates = {}
        try:
            for name, vector in queries:
                hits = self.qdrant.query_points(collection_name(), using=name, query=[vector],
                    query_filter=allowed, limit=window, with_payload=True,
                    with_vectors=["text"] if name == "text" else False,
                    score_threshold=None if source_id else (settings.SEMANTIC_CANDIDATE_MIN if name == "text" else settings.VISUAL_CANDIDATE_MIN)).points
                for rank, hit in enumerate(hits, 1):
                    item = candidates.setdefault(str(hit.id), {"score": 0.0, "metadata": {}})
                    item["score"] += 1 / (60 + rank)
                    item["metadata"][name + "_similarity"] = float(hit.score)
                    if name == "text":
                        chunks = (hit.payload or {}).get("passages", [])
                        vectors = (hit.vector or {}).get("text", [])
                        if chunks and len(chunks) == len(vectors):
                            best = max(range(len(vectors)), key=lambda i: sum(a*b for a,b in zip(vector, vectors[i])))
                            item["metadata"]["matched_passage"] = chunks[best]
            ordered = sorted(candidates.items(), key=lambda pair: (-pair[1]["score"], pair[0]))
            ranked = [RankedItem(id=key, rank=rank, raw_score=value["score"], metadata=value["metadata"])
                      for rank, (key, value) in enumerate(ordered, 1)]
            return ranked[offset:offset+limit], len(ranked)
        except Exception as exc:
            logger.exception("Multimodal retrieval failed")
            raise HTTPException(503, "Multimodal search index is unavailable") from exc

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
                response = await run_in_threadpool(self.qdrant.query_points,
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
                search_result = await run_in_threadpool(self.qdrant.search,
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
