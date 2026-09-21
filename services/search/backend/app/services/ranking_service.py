import math
from typing import List, Dict
from datetime import datetime, timezone
from app.utils.rrf import FusionResult
from app.models.file_metadata import FileMetadata

# Fused RRF scores are small (about 0.008-0.016) and neighbouring ranks differ by ~1%.
# Boosts are therefore bounded multipliers, so popularity and recency can only reorder
# results of near-equal relevance. Additive bonuses of 0.005-0.02 (the old scheme) were
# larger than the whole RRF range and let a popular file outrank a far better match.
MAX_RECENCY_BOOST = 0.015  # newly ingested, decays linearly to 0 over RECENCY_DAYS
MAX_POPULARITY_BOOST = 0.035  # log-scaled, saturates at POPULARITY_SATURATION events
RECENCY_DAYS = 180.0
POPULARITY_SATURATION = 100


class RankingService:
    """
    Applies bounded contextual boosts (recency, popularity) to fused results.
    """
    def rank_and_adjust(
        self,
        fused_results: List[FusionResult],
        files_map: Dict[str, FileMetadata]
    ) -> List[FusionResult]:
        now = datetime.now(timezone.utc)

        for item in fused_results:
            file = files_map.get(item.id)
            if not file:
                continue
            boost = 1.0

            if file.ingested_at:
                ingested_utc = file.ingested_at.replace(tzinfo=timezone.utc) if file.ingested_at.tzinfo is None else file.ingested_at
                age_days = (now - ingested_utc).total_seconds() / 86400.0
                boost += MAX_RECENCY_BOOST * max(0.0, 1.0 - age_days / RECENCY_DAYS)

            events = 2 * (file.download_count or 0) + (file.file_preview_count or 0)
            boost += MAX_POPULARITY_BOOST * min(
                1.0, math.log1p(events) / math.log1p(POPULARITY_SATURATION)
            )
            item.rrf_score *= boost

        # Re-sort after fine-tuning
        fused_results.sort(key=lambda x: x.rrf_score, reverse=True)
        return fused_results

_ranking_service = RankingService()

def get_ranking_service() -> RankingService:
    return _ranking_service
