from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, update, desc
from app.models.file_metadata import FileMetadata
from app.schemas.filters import SearchFilters, FacetsResponse, FacetCountItem
from app.utils.filters import build_sqlalchemy_filters
from app.utils.query_normalizer import tokenize

class FileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, file_id: str) -> Optional[FileMetadata]:
        stmt = select(FileMetadata).where(FileMetadata.file_id == file_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_ids(self, file_ids: List[str]) -> List[FileMetadata]:
        if not file_ids:
            return []
        stmt = select(FileMetadata).where(FileMetadata.file_id.in_(file_ids))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_keyword(
        self,
        query: str,
        filters: Optional[SearchFilters] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Tuple[FileMetadata, float]], int]:
        """
        Performs keyword full-text / term matching across title, description, tags, OCR, transcript, summary.
        Computes match score based on term frequency and field importance.
        """
        filter_clauses = build_sqlalchemy_filters(filters)
        
        if query.lower() in ["all", "*", ""]:
            tokens = []
        else:
            tokens = tokenize(query)

        if not tokens:
            # If no tokens or wildcard, return filtered files sorted by ingested_at
            stmt = select(FileMetadata).where(*filter_clauses).order_by(desc(FileMetadata.ingested_at)).offset(offset).limit(limit)
            count_stmt = select(func.count(FileMetadata.file_id)).where(*filter_clauses)
            
            res = await self.db.execute(stmt)
            count_res = await self.db.execute(count_stmt)
            files = list(res.scalars().all())
            total = count_res.scalar() or 0
            return [(f, 1.0) for f in files], total

        # Build term match conditions across fields
        match_conditions = []
        for token in tokens:
            t_pattern = f"%{token}%"
            match_conditions.append(
                or_(
                    FileMetadata.title.ilike(t_pattern),
                    FileMetadata.description.ilike(t_pattern),
                    FileMetadata.file_name.ilike(t_pattern),
                    FileMetadata.category.ilike(t_pattern),
                    FileMetadata.content_summary.ilike(t_pattern),
                    FileMetadata.ocr_text.ilike(t_pattern),
                    FileMetadata.transcript.ilike(t_pattern),
                    FileMetadata.caption.ilike(t_pattern)
                )
            )

        query_clauses = filter_clauses + [or_(*match_conditions)]
        
        # Execute query
        stmt = select(FileMetadata).where(*query_clauses)
        res = await self.db.execute(stmt)
        all_matches = list(res.scalars().all())
        total = len(all_matches)

        # Score matches in Python by token hits & field weights
        scored_results: List[Tuple[FileMetadata, float]] = []
        for file in all_matches:
            score = 0.0
            t_lower = (file.title or "").lower()
            d_lower = (file.description or "").lower()
            c_lower = (file.caption or "").lower()
            ocr_lower = (file.ocr_text or "").lower()
            tr_lower = (file.transcript or "").lower()
            sum_lower = (file.content_summary or "").lower()
            cat_lower = (file.category or "").lower()
            
            for token in tokens:
                if token in t_lower:
                    score += 5.0
                if token in cat_lower:
                    score += 4.0
                if token in c_lower:
                    score += 3.0
                if token in sum_lower:
                    score += 2.5
                if token in d_lower:
                    score += 2.0
                if token in ocr_lower:
                    score += 1.5
                if token in tr_lower:
                    score += 1.5
                if file.tags and any(token in str(t).lower() for t in file.tags):
                    score += 3.0

            scored_results.append((file, score))

        # Sort descending by score
        scored_results.sort(key=lambda x: x[1], reverse=True)
        paginated = scored_results[offset : offset + limit]
        return paginated, total

    async def compute_facets(self, query: str = "", filters: Optional[SearchFilters] = None) -> FacetsResponse:
        """
        Computes dynamic facet counts (file types, categories, AI generated, PII, datasets, top tags).
        """
        filter_clauses = build_sqlalchemy_filters(filters)
        
        if query:
            tokens = tokenize(query)
            if tokens:
                match_conditions = [
                    or_(
                        FileMetadata.title.ilike(f"%{t}%"),
                        FileMetadata.description.ilike(f"%{t}%"),
                        FileMetadata.caption.ilike(f"%{t}%"),
                        FileMetadata.ocr_text.ilike(f"%{t}%"),
                        FileMetadata.transcript.ilike(f"%{t}%")
                    ) for t in tokens
                ]
                filter_clauses.append(or_(*match_conditions))

        # Query all matching records to aggregate facets
        stmt = select(FileMetadata).where(*filter_clauses)
        res = await self.db.execute(stmt)
        files = list(res.scalars().all())

        file_types_count: Dict[str, int] = {}
        categories_count: Dict[str, int] = {}
        datasets_count: Dict[str, int] = {}
        ai_count: Dict[str, int] = {"AI-Generated": 0, "Human / Authentic": 0}
        pii_count: Dict[str, int] = {"PII Detected": 0, "No PII (Safe)": 0}
        tags_count: Dict[str, int] = {}

        for f in files:
            file_types_count[f.file_type] = file_types_count.get(f.file_type, 0) + 1
            categories_count[f.category] = categories_count.get(f.category, 0) + 1
            datasets_count[f.dataset_name] = datasets_count.get(f.dataset_name, 0) + 1
            
            if f.ai_generated:
                ai_count["AI-Generated"] += 1
            else:
                ai_count["Human / Authentic"] += 1
                
            if f.pii_detected:
                pii_count["PII Detected"] += 1
            else:
                pii_count["No PII (Safe)"] += 1

            if f.tags and isinstance(f.tags, list):
                for tag in f.tags:
                    tags_count[tag] = tags_count.get(tag, 0) + 1

        top_tags_sorted = sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:15]

        return FacetsResponse(
            file_types=[FacetCountItem(value=k, count=v) for k, v in file_types_count.items()],
            categories=[FacetCountItem(value=k, count=v) for k, v in sorted(categories_count.items(), key=lambda x: x[1], reverse=True)],
            datasets=[FacetCountItem(value=k, count=v) for k, v in sorted(datasets_count.items(), key=lambda x: x[1], reverse=True)],
            ai_generated=[FacetCountItem(value=k, count=v) for k, v in ai_count.items() if v > 0],
            pii_detected=[FacetCountItem(value=k, count=v) for k, v in pii_count.items() if v > 0],
            top_tags=[FacetCountItem(value=k, count=v) for k, v in top_tags_sorted],
            total_matches=len(files)
        )

    async def increment_preview_count(self, file_id: str):
        stmt = update(FileMetadata).where(FileMetadata.file_id == file_id).values(
            file_preview_count=FileMetadata.file_preview_count + 1
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def increment_download_count(self, file_id: str):
        stmt = update(FileMetadata).where(FileMetadata.file_id == file_id).values(
            download_count=FileMetadata.download_count + 1
        )
        await self.db.execute(stmt)
        await self.db.commit()
