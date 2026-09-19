from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from ingestion.api.router_ingestion import _run_response
from ingestion.models.ingestion_run import IngestionRun


def test_completed_run_response_calculates_wall_throughput():
    started = datetime(2026, 9, 19, tzinfo=UTC)
    run = IngestionRun(
        id=uuid4(),
        connector_id=uuid4(),
        source_type="S3",
        status="completed",
        triggered_at=started,
        completed_at=started + timedelta(seconds=10),
        enumerated_count=20,
        metadata_files_skipped=2,
        terminal_count=20,
        succeeded_count=18,
        duplicate_count=1,
        skipped_count=1,
        rejected_count=0,
        failed_count=0,
        transient_retry_count=0,
        bytes_processed=10 * 1024 * 1024,
        enumeration_stats={},
    )

    response = _run_response(run)

    assert response.elapsed_seconds == 10
    assert response.mib_per_second == 1
    assert response.objects_per_second == 2
