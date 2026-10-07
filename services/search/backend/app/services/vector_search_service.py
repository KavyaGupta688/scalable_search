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

# Filter sets (as JSON) recently found to exceed VECTOR_EXACT_GATE_MAX -> expiry time.
_LARGE_FILTER_SETS: Dict[str, float] = {}


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

    def _eligible_ids(self, filters, exclude_id=None):
        """Visible ids matching the filters, or None when there are more than the exact gate.

        Up to VECTOR_EXACT_GATE_MAX ids are sent to Qdrant as a HasId list, which is exact.
        Beyond that the list is too large to send, so callers fall back to Qdrant payload
        filters and verify each hit in SQL (see _verify_visible).
        """
        from sqlalchemy import select
        from modules.shared.integration import database_engine
        from app.models.file_metadata import FileMetadata
        from app.utils.filters import build_sqlalchemy_filters

        import time

        # A filter set seen to exceed the gate skips enumeration for a while: reading
        # gate+1 ids only to discard them would cost every broad query a large scan.
        key = filters.model_dump_json() if filters else ""
        if _LARGE_FILTER_SETS.get(key, 0) > time.monotonic():
            return None
        gate = settings.VECTOR_EXACT_GATE_MAX
        stmt = select(FileMetadata.file_id).where(*build_sqlalchemy_filters(filters))
        if exclude_id:
            stmt = stmt.where(FileMetadata.file_id != exclude_id)
        with database_engine("search").connect() as conn:
            ids = list(conn.execute(stmt.limit(gate + 1)).scalars())
        if len(ids) > gate:
            if len(_LARGE_FILTER_SETS) > 1000:
                _LARGE_FILTER_SETS.clear()
            _LARGE_FILTER_SETS[key] = time.monotonic() + 300
            return None
        return ids

    @staticmethod
    def _verify_visible(ids, filters):
        """The subset of `ids` that SQL says is visible and matches every filter.

        Always the primary database: a replica lagging a licence revocation must not
        re-admit a document.
        """
        from sqlalchemy import select
        from modules.shared.integration import database_engine
        from app.models.file_metadata import FileMetadata
        from app.utils.filters import build_sqlalchemy_filters

        if not ids:
            return set()
        stmt = select(FileMetadata.file_id).where(
            FileMetadata.file_id.in_(list(ids)), *build_sqlalchemy_filters(filters)
        )
        with database_engine("search").connect() as conn:
            return set(conn.execute(stmt).scalars())

    def _fetch_verified(self, search, need, batch, filters, id_of):
        """Hits from `search(limit, offset)` that pass the SQL check, best first.

        Keeps fetching further batches until `need` verified hits are found, Qdrant runs
        out of matches, or VECTOR_MAX_ROUNDS is reached. A query whose first batch is
        mostly visible (the normal case) costs one round, as before.
        """
        kept, offset = [], 0
        for _ in range(max(1, settings.VECTOR_MAX_ROUNDS)):
            hits = search(batch, offset)
            visible = self._verify_visible([id_of(hit) for hit in hits], filters)
            kept.extend(hit for hit in hits if id_of(hit) in visible)
            if len(kept) >= need or len(hits) < batch:
                break
            offset += batch
        return kept[:need]

    def _multimodal_search(self, query, filters, limit, offset, source_id=None):
        # Canonical SQL remains authoritative for entitlement and every user filter.
        eligible = self._eligible_ids(filters, exclude_id=source_id)
        from app.core.metrics import VECTOR_GATE
        VECTOR_GATE.labels(path="payload" if eligible is None else "exact").inc()
        if eligible is None:
            return self._retrieve_multimodal(query, None, limit, offset, source_id, filters=filters)
        if not eligible:
            return [], 0
        return self._retrieve_multimodal(query, eligible, limit, offset, source_id)

    def _retrieve_multimodal(self, query, eligible, limit, offset, source_id=None, filters=None):
        """Retrieve only caller-authorized IDs; also usable for offline quality evaluation.

        `eligible` is the exact id list, or None for a catalogue too large to enumerate, in
        which case Qdrant payload filters narrow the candidates and SQL verifies them.
        """
        from modules.shared.semantic_index import collection_name, encode_passages, VERSION
        from modules.shared.vector_store import search_params
        from fastapi import HTTPException
        from app.utils.filters import build_qdrant_filter
        if eligible is not None and not eligible:
            return [], 0
        version = qmodels.FieldCondition(key="representation_version", match=qmodels.MatchValue(value=VERSION))
        window = max(settings.VECTOR_CANDIDATES, limit + offset)
        if eligible is not None:
            allowed = qmodels.Filter(must=[qmodels.HasIdCondition(has_id=eligible), version])
            fetch = window
        else:
            allowed = build_qdrant_filter(filters)
            allowed.must.append(version)
            if source_id:
                allowed.must_not = (allowed.must_not or []) + [qmodels.HasIdCondition(has_id=[source_id])]
            # Some payload-matched hits fail the SQL check; over-fetch so the window stays full.
            fetch = window * settings.VECTOR_OVERFETCH
        queries = None
        if source_id:
            points = self.qdrant.retrieve(collection_name(), ids=[source_id], with_vectors=True)
            if points:
                vectors = points[0].vector
                name = "visual" if vectors.get("visual") else "text"
                if vectors.get(name):
                    queries = [(name, vectors[name][0])]
        if queries is None:
            from app.clients.embedding_client import passage_query_embedding
            queries = [("text", passage_query_embedding(query)),
                       ("visual", self.embedder.generate_text_embedding(query))]
        candidates = {}
        try:
            for name, vector in queries:
                def search(limit_, offset_, name=name, vector=vector):
                    return self.qdrant.query_points(collection_name(), using=name, query=[vector],
                        query_filter=allowed, limit=limit_, offset=offset_, with_payload=True,
                        with_vectors=["text"] if name == "text" else False,
                        search_params=search_params(),
                        score_threshold=None if source_id else (settings.SEMANTIC_CANDIDATE_MIN if name == "text" else settings.VISUAL_CANDIDATE_MIN)).points
                if eligible is None:
                    hits = self._fetch_verified(search, window, fetch, filters, lambda hit: str(hit.id))
                else:
                    hits = search(fetch, 0)
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
        from modules.shared.vector_store import search_params

        from app.core.metrics import VECTOR_GATE

        eligible = await run_in_threadpool(self._eligible_ids, filters, exclude_id)
        VECTOR_GATE.labels(path="payload" if eligible is None else "exact").inc()
        if eligible is not None and not eligible:
            return [], 0
        qdrant_filter = build_qdrant_filter(filters)
        fetch = limit + offset
        if eligible is not None:
            qdrant_filter.must.append(qmodels.HasIdCondition(has_id=eligible))
        else:
            # Too many ids to send: payload filters narrow, SQL verifies after retrieval.
            fetch *= settings.VECTOR_OVERFETCH

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

        def search(limit_, offset_):
            # query_points needs qdrant-client >= 1.10; older clients only have search.
            if hasattr(self.qdrant, "query_points"):
                response = self.qdrant.query_points(
                    collection_name=self.collection_name,
                    query=vector,
                    query_filter=qdrant_filter,
                    limit=limit_,
                    offset=offset_,
                    with_payload=True,
                    search_params=search_params(),
                )
                return response.points if hasattr(response, "points") else response
            return self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=qdrant_filter,
                limit=limit_,
                offset=offset_,
                with_payload=True,
                search_params=search_params(),
            )

        def hit_id(hit):
            return (getattr(hit, "payload", None) or {}).get("file_id") or str(getattr(hit, "id", ""))

        try:
            if eligible is None:
                search_result = await run_in_threadpool(
                    self._fetch_verified, search, limit + offset, fetch, filters, hit_id
                )
                # Matches of the same payload filter; equals the visible count whenever
                # payloads are current (the outbox refreshes them within seconds).
                total_hits = (await run_in_threadpool(
                    self.qdrant.count, self.collection_name, count_filter=qdrant_filter, exact=True
                )).count
            else:
                search_result = await run_in_threadpool(search, fetch, 0)
                total_hits = len(eligible)

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

            return ranked_items, total_hits

        except Exception as e:
            logger.error(f"Error querying Qdrant: {e}", exc_info=True)
            from fastapi import HTTPException

            raise HTTPException(503, "Vector search is unavailable") from e
