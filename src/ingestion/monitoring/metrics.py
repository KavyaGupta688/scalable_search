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

METRICS = MetricsNamespace()

def setup_metrics_endpoint(app: FastAPI) -> None:
    """Adds a GET /metrics route to the FastAPI app."""
    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
