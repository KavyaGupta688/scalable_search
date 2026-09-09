from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

class MetricsNamespace:
    """Namespace for Prometheus metrics."""
    FILES_PROCESSED_TOTAL = Counter(
        'ingestion_files_processed_total', 
        'Total number of files processed',
        ['source_type', 'outcome']
    )
    
    FILES_FAILED_TOTAL = Counter(
        'ingestion_files_failed_total', 
        'Total number of files that failed processing',
        ['source_type', 'failure_type']
    )
    
    PROCESSING_DURATION_SECONDS = Histogram(
        'ingestion_processing_duration_seconds', 
        'Time taken to process files',
        ['source_type', 'stage']
    )

    ENUMERATION_PAGES_TOTAL = Counter(
        'ingestion_enumeration_pages_total',
        'S3 ListObjectsV2 pages read',
        ['source_type']
    )

    ENUMERATION_OBJECTS_TOTAL = Counter(
        'ingestion_enumeration_objects_total',
        'Objects yielded by the enumerator',
        ['source_type']
    )

    ENUMERATION_LIMIT_REACHED_TOTAL = Counter(
        'ingestion_enumeration_limit_reached_total',
        'Enumerations stopped by an explicit max_objects safety cap',
        ['source_type']
    )

    PROCESS_MEMORY_PEAK_BYTES = Gauge(
        'ingestion_process_memory_peak_bytes',
        'Peak resident memory reported by the current process'
    )
    
    THROUGHPUT_BYTES_TOTAL = Counter(
        'ingestion_throughput_bytes_total', 
        'Total bytes processed',
        ['source_type']
    )
    
    QUEUE_DEPTH = Gauge(
        'ingestion_queue_depth', 
        'Kafka consumer lag or current queue depth'
    )
    
    CIRCUIT_BREAKER_STATE = Gauge(
        'ingestion_circuit_breaker_state', 
        'State of circuit breaker (0=closed, 1=open, 2=half-open)'
    )
    
    DB_QUERY_DURATION_SECONDS = Histogram(
        'ingestion_db_query_duration_seconds', 
        'Time taken for database queries'
    )
    
    ACTIVE_UPLOADS = Gauge(
        'ingestion_active_uploads', 
        'Number of currently active file uploads'
    )
    
    MINIO_ERRORS_TOTAL = Counter(
        'ingestion_minio_errors_total', 
        'Total number of MinIO/S3 related errors'
    )

    RETENTION_LIFECYCLE_APPLY_TOTAL = Counter(
        'ingestion_retention_lifecycle_apply_total',
        'Attempts to install or verify the managed MinIO lifecycle rules',
        ['outcome']
    )

    RETENTION_RECONCILIATION_RUNS_TOTAL = Counter(
        'ingestion_retention_reconciliation_runs_total',
        'Retention reconciliation runs',
        ['outcome']
    )

    RETENTION_OBJECTS_TOTAL = Counter(
        'ingestion_retention_objects_total',
        'Objects observed or acted on by retention reconciliation',
        ['outcome']
    )

    RETENTION_EXPIRED_PENDING = Gauge(
        'ingestion_retention_expired_pending',
        'Database records past expiry whose deletion is not confirmed'
    )

    RETENTION_ACTIVE_MISSING = Gauge(
        'ingestion_retention_active_missing',
        'Active non-expired database records whose MinIO content is missing'
    )

    RETENTION_LIFECYCLE_CONFIGURED = Gauge(
        'ingestion_retention_lifecycle_configured',
        'Whether the managed lifecycle policy was installed successfully'
    )

    RETENTION_ENFORCEMENT_ENABLED = Gauge(
        'ingestion_retention_enforcement_enabled',
        'Whether retention processing is enabled (dry-run or enforcing)'
    )

    RETENTION_LAST_SUCCESS_TIMESTAMP = Gauge(
        'ingestion_retention_last_success_timestamp_seconds',
        'Unix timestamp of the last successful retention reconciliation'
    )

    RETENTION_RECONCILIATION_DURATION_SECONDS = Histogram(
        'ingestion_retention_reconciliation_duration_seconds',
        'Duration of retention reconciliation runs'
    )

METRICS = MetricsNamespace()

def setup_metrics_endpoint(app: FastAPI) -> None:
    """Adds a GET /metrics route to the FastAPI app."""
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
