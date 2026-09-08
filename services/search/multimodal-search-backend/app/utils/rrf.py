from typing import Dict, List, Any, Optional
from pydantic import BaseModel

class RankedItem(BaseModel):
    id: str
    rank: int
    raw_score: float
    metadata: Dict[str, Any] = {}

class FusionResult(BaseModel):
    id: str
    rrf_score: float
    keyword_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    text_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    match_sources: List[str] = []

def reciprocal_rank_fusion(
    keyword_results: List[RankedItem],
    vector_results: List[RankedItem],
    k: int = 60,
    keyword_weight: float = 0.5,
    vector_weight: float = 0.5
) -> List[FusionResult]:
    """
    Applies Reciprocal Rank Fusion (RRF) to merge and rank results from keyword and vector retrieval paths.
    Formula: RRF(d) = sum_m ( w_m / (k + rank_m(d)) )
    """
    scores: Dict[str, Dict[str, Any]] = {}

    # Process keyword ranked items
    for item in keyword_results:
        doc_id = item.id
        rank = item.rank
        contribution = keyword_weight * (1.0 / (k + rank))
        
        if doc_id not in scores:
            scores[doc_id] = {
                "id": doc_id,
                "rrf_score": 0.0,
                "keyword_rank": rank,
                "vector_rank": None,
                "text_score": item.raw_score,
                "vector_similarity": None,
                "match_sources": ["keyword"]
            }
        else:
            scores[doc_id]["keyword_rank"] = rank
            scores[doc_id]["text_score"] = item.raw_score
            if "keyword" not in scores[doc_id]["match_sources"]:
                scores[doc_id]["match_sources"].append("keyword")
        
        scores[doc_id]["rrf_score"] += contribution

    # Process vector ranked items
    for item in vector_results:
        doc_id = item.id
        rank = item.rank
        contribution = vector_weight * (1.0 / (k + rank))
        
        if doc_id not in scores:
            scores[doc_id] = {
                "id": doc_id,
                "rrf_score": 0.0,
                "keyword_rank": None,
                "vector_rank": rank,
                "text_score": None,
                "vector_similarity": item.raw_score,
                "match_sources": ["vector"]
            }
        else:
            scores[doc_id]["vector_rank"] = rank
            scores[doc_id]["vector_similarity"] = item.raw_score
            if "vector" not in scores[doc_id]["match_sources"]:
                scores[doc_id]["match_sources"].append("vector")
        
        scores[doc_id]["rrf_score"] += contribution

    # Sort items descending by combined RRF score
    sorted_items = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    return [FusionResult(**item) for item in sorted_items]
