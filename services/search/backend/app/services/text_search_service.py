from typing import List, Tuple, Optional, Dict
from app.repositories.file_repository import FileRepository
from app.models.file_metadata import FileMetadata
from app.schemas.filters import SearchFilters
from app.utils.rrf import RankedItem

class TextSearchService:
    def __init__(self, file_repo: FileRepository):
        self.file_repo = file_repo

    async def search(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 50,
        offset: int = 0,
        match_all: bool = True
    ) -> Tuple[List[RankedItem], int, Dict[str, FileMetadata]]:
        """
        Executes full-text keyword search and returns ranked items.
        """
        scored_files, total = await self.file_repo.search_keyword(
            query=query,
            filters=filters,
            limit=limit,
            offset=offset, match_all=match_all
        )

        ranked_items: List[RankedItem] = []
        files_map: Dict[str, FileMetadata] = {}

        for rank_idx, (file, score) in enumerate(scored_files, start=1):
            files_map[file.file_id] = file
            ranked_items.append(
                RankedItem(
                    id=file.file_id,
                    rank=rank_idx,
                    raw_score=score,
                    metadata={"title": file.title, "file_name": file.file_name}
                )
            )

        return ranked_items, total, files_map
