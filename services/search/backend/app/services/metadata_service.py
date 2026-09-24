from typing import List, Dict, Optional
from app.repositories.file_repository import FileRepository
from app.models.file_metadata import FileMetadata
from app.schemas.file import FileMetadataRead, FilePreviewResponse, TechnicalMetadata, AIMetadata
from app.schemas.search import SearchResultItem, SearchResultScoreInfo
from app.utils.rrf import FusionResult
from app.core.exceptions import ResourceNotFoundException

class MetadataService:
    def __init__(self, file_repo: FileRepository):
        self.file_repo = file_repo

    async def get_file_preview(self, file_id: str) -> FilePreviewResponse:
        file = await self.file_repo.get_by_id(file_id)
        if not file:
            raise ResourceNotFoundException("File", file_id)

        # Track preview event counter
        await self.file_repo.increment_preview_count(file_id)

        return FilePreviewResponse(
            file_id=file.file_id,
            title=file.title,
            file_name=file.file_name,
            file_type=file.file_type,
            category=file.category,
            dataset_name=file.dataset_name,
            thumbnail_url=file.thumbnail_url,
            preview_url=file.preview_url,
            description=file.description,
            caption=file.caption,
            ocr_text=file.ocr_text,
            transcript=file.transcript,
            content_summary=file.content_summary,
            tags=file.tags or [],
            technical=TechnicalMetadata(
                file_size=file.file_size,
                mime_type=file.mime_type,
                width=file.width,
                height=file.height,
                duration=file.duration,
                source_batch=file.source_batch,
                checksum=file.checksum
            ),
            ai_enrichment=AIMetadata(
                content_summary=file.content_summary,
                ocr_text=file.ocr_text,
                transcript=file.transcript,
                caption=file.caption,
                pii_detected=file.pii_detected,
                nsfw_detected=file.nsfw_detected,
                ai_generated=file.ai_generated,
                embedding_model=file.embedding_model,
                embedding_version=file.embedding_version,
                embedding_status=file.embedding_status
            ),
            download_count=file.download_count,
            preview_count=file.file_preview_count
        )

    async def hydrate_results(
        self,
        ranked_items: List[FusionResult],
        prefetched_files: Optional[Dict[str, FileMetadata]] = None
    ) -> List[SearchResultItem]:
        """
        Hydrates fusion ranked items with complete metadata from DB.
        """
        prefetched = prefetched_files or {}
        missing_ids = [item.id for item in ranked_items if item.id not in prefetched]
        
        if missing_ids:
            fetched_files = await self.file_repo.get_by_ids(missing_ids)
            for f in fetched_files:
                prefetched[f.file_id] = f

        hydrated: List[SearchResultItem] = []
        for item in ranked_items:
            file = prefetched.get(item.id)
            if not file:
                continue

            # Create snippets
            ocr_snip = (file.ocr_text[:160] + "...") if file.ocr_text and len(file.ocr_text) > 160 else file.ocr_text
            tr_snip = (file.transcript[:160] + "...") if file.transcript and len(file.transcript) > 160 else file.transcript

            score_info = SearchResultScoreInfo(
                rrf_score=round(item.rrf_score, 4),
                keyword_rank=item.keyword_rank,
                vector_rank=item.vector_rank,
                vector_similarity=round(item.vector_similarity, 3) if item.vector_similarity is not None else None,
                text_score=round(item.text_score, 2) if item.text_score is not None else None,
                visual_similarity=item.visual_similarity,
                semantic_similarity=item.semantic_similarity,
                match_sources=item.match_sources
            )

            hydrated.append(
                SearchResultItem(
                    file_id=file.file_id,
                    dataset_id=file.dataset_id,
                    dataset_name=file.dataset_name,
                    file_name=file.file_name,
                    file_type=file.file_type,
                    title=file.title,
                    description=file.description,
                    caption=file.caption,
                    content_summary=file.content_summary,
                    ocr_snippet=ocr_snip,
                    transcript_snippet=tr_snip,
                    tags=file.tags or [],
                    category=file.category,
                    thumbnail_url=file.thumbnail_url,
                    preview_url=file.preview_url,
                    file_size=file.file_size,
                    duration=file.duration,
                    width=file.width,
                    height=file.height,
                    ai_generated=file.ai_generated,
                    pii_detected=file.pii_detected,
                    ingested_at=file.ingested_at,
                    score_info=score_info,
                    download_count=file.download_count,
                    file_preview_count=file.file_preview_count
                )
            )

        return hydrated
