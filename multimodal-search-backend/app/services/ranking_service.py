from typing import List, Dict
from datetime import datetime, timezone
from app.utils.rrf import FusionResult
from app.models.file_metadata import FileMetadata

class RankingService:
    """
    Ranks top results with contextual boosts (popularity bonus, recency decay, cross-modal affinity).
    """
    def rank_and_adjust(
        self,
        fused_results: List[FusionResult],
        files_map: Dict[str, FileMetadata]
    ) -> List[FusionResult]:
        now = datetime.now(timezone.utc)
        
        for item in fused_results:
            file = files_map.get(item.id)
            if file:
                # Recency bonus (within 30 days gets a small boost)
                if file.ingested_at:
                    ingested_utc = file.ingested_at.replace(tzinfo=timezone.utc) if file.ingested_at.tzinfo is None else file.ingested_at
                    age_days = (now - ingested_utc).total_seconds() / 86400.0
                    recency_boost = max(0.0, 0.005 * (1.0 - (age_days / 180.0)))
                    item.rrf_score += recency_boost

                # Popularity bonus (downloads / previews)
                pop_bonus = min(0.02, (file.download_count * 0.001) + (file.file_preview_count * 0.0005))
                item.rrf_score += pop_bonus

        # Re-sort after fine-tuning
        fused_results.sort(key=lambda x: x.rrf_score, reverse=True)
        return fused_results

_ranking_service = RankingService()

def get_ranking_service() -> RankingService:
    return _ranking_service
