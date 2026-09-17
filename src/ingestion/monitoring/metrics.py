from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest


class MetricsNamespace:
    """Namespace for Prometheus metrics."""

    FILES_PROCESSED_TOTAL = Counter(
        "ingestion_files_processed_total", "Total number of files processed", ["source_type", "outcome"]
    )

    FILES_FAILED_TOTAL = Counter(
        "ingestion_files_failed_total", "Total number of files that failed processing", ["source_type", "failure_type"]
    )

    PROCESSING_DURATION_SECONDS = Histogram(
        "ingestion_processing_duration_seconds", "Time taken to process files", ["source_type", "stage"]
    )

    ENUMERATION_PAGES_TOTAL = Counter(
        "ingestion_enumeration_pages_total", "S3 ListObjectsV2 pages read", ["source_type"]
    )

    ENUMERATION_OBJECTS_TOTAL = Counter(
        "ingestion_enumeration_objects_total", "Objects yielded by the enumerator", ["source_type"]
    )

    ENUMERATION_LIMIT_REACHED_TOTAL = Counter(
        "ingestion_enumeration_limit_reached_total",
        "Enumerations stopped by an explicit max_objects safety cap",
        ["source_type"],
    )

    PROCESS_MEMORY_PEAK_BYTES = Gauge(
        "ingestion_process_memory_peak_bytes", "Peak resident memory reported by the current process"
    )

    THROUGHPUT_BYTES_TOTAL = Counter("ingestion_throughput_bytes_total", "Total bytes processed", ["source_type"])

    QUEUE_DEPTH = Gauge("ingestion_queue_depth", "Kafka consumer lag or current queue depth")

    DB_QUERY_DURATION_SECONDS = Histogram("ingestion_db_query_duration_seconds", "Time taken for database queries")

    RETENTION_RECONCILIATION_RUNS_TOTAL = Counter(
        "ingestion_retention_reconciliation_runs_total", "Retention reconciliation runs", ["outcome"]
    )

    RETENTION_OBJECTS_TOTAL = Counter(
        "ingestion_retention_objects_total",
        "Licence records observed or acted on by expiry reconciliation",
        ["outcome"],
    )

    RETENTION_EXPIRED_PENDING = Gauge(
        "ingestion_retention_expired_pending", "Active entitlement records whose expiry status is not yet reconciled"
    )

    RETENTION_ENFORCEMENT_ENABLED = Gauge(
        "ingestion_retention_enforcement_enabled", "Whether licence-expiry reconciliation is enabled"
    )

    RETENTION_LAST_SUCCESS_TIMESTAMP = Gauge(
        "ingestion_retention_last_success_timestamp_seconds",
        "Unix timestamp of the last successful retention reconciliation",
    )

    RETENTION_RECONCILIATION_DURATION_SECONDS = Histogram(
        "ingestion_retention_reconciliation_duration_seconds", "Duration of retention reconciliation runs"
    )


METRICS = MetricsNamespace()


def setup_metrics_endpoint(app: FastAPI) -> None:
    """Adds a GET /metrics route to the FastAPI app."""

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
