"""Publication policy for persisted AI safety results, independent of model imports."""
import math


def safety_cleared(safety, toxicity_threshold=0.8):
    if not isinstance(safety, dict) or not safety:
        return False
    if safety.get("nsfw_flagged") or safety.get("analysis_incomplete"):
        return False
    try:
        toxicity = float(safety.get("toxicity_score", 0.0))
    except (TypeError, ValueError):
        return False
    # PII is an annotation/filter, not a publication veto in AI revision 5a54af9.
    return math.isfinite(toxicity) and toxicity < toxicity_threshold
