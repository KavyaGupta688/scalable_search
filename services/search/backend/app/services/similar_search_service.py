from typing import List, Optional, Tuple
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.services.vector_search_service import VectorSearchService
from app.repositories.file_repository import FileRepository
from app.core.config import get_settings
from app.schemas.filters import SearchFilters
from app.utils.rrf import RankedItem
from app.core.exceptions import ResourceNotFoundException

logger = logging.getLogger(__name__)
settings = get_settings()

class SimilarSearchService:
    def __init__(
        self,
        qdrant_client: QdrantClient,
        vector_search_service: VectorSearchService,
        file_repo: FileRepository
    ):
        self.qdrant = qdrant_client
        self.vector_search_service = vector_search_service
        self.file_repo = file_repo
        self.collection_name = settings.QDRANT_COLLECTION_NAME

    async def find_similar(
        self,
        file_id: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 10
    ) -> Tuple[List[RankedItem], int]:
        """
        Finds files semantically and visually similar to target file_id, excluding the original.
        """
        target_file = await self.file_repo.get_by_id(file_id)
        if not target_file:
            raise ResourceNotFoundException("File", file_id)

        if settings.USE_MULTIMODAL_INDEX:
            from starlette.concurrency import run_in_threadpool
            return await run_in_threadpool(self.vector_search_service._multimodal_search,
                target_file.title, filters, limit, 0, file_id)

        vector = None
        # Try finding vector in Qdrant by payload match
        try:
            points = self.qdrant.scroll(
                collection_name=self.collection_name,
                scroll_filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(key="file_id", match=qmodels.MatchValue(value=file_id))]
                ),
                limit=1,
                with_vectors=True
            )
            if points and points[0] and len(points[0]) > 0:
                vector = points[0][0].vector
        except Exception as e:
            logger.debug(f"Scroll for vector on {file_id} failed: {e}")

        # If not found in Qdrant or vector is None, compute from metadata
        if vector is None:
            query_text = f"{target_file.title} {target_file.category} {target_file.description or ''} {target_file.caption or ''} {' '.join(target_file.tags or [])}"
            vector = self.vector_search_service.embedder.generate_text_embedding(query_text)

        # Execute vector search excluding target file_id
        results, total = await self.vector_search_service.search_by_vector(
            vector=vector,
            filters=filters,
            limit=limit,
            offset=0,
            exclude_id=file_id
        )

        filtered_results = [r for r in results if r.id != file_id]
        return filtered_results, len(filtered_results)
