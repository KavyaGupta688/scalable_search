"""Prometheus metrics for the Search service, served at /metrics (one series per replica)."""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SEARCH_LATENCY = Histogram(
    "search_request_duration_seconds",
    "End-to-end search latency by mode",
    ["mode"],
    buckets=(0.05, 0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5, 10),
)
STAGE_LATENCY = Histogram(
    "search_stage_duration_seconds",
    "Latency of one search stage (keyword, vector, rerank, facets)",
    ["stage"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
DEGRADED = Counter(
    "search_degraded_total",
    "Searches answered without one of their components",
    ["component"],
)
CACHE_REQUESTS = Counter(
    "search_cache_requests_total", "Search cache lookups", ["cache", "outcome"]
)
VECTOR_GATE = Counter(
    "search_vector_gate_total",
    "Vector retrievals by licence-gate path (exact id list or payload filter)",
    ["path"],
)


def render():
    return generate_latest(), CONTENT_TYPE_LATEST
