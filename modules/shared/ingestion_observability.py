"""Read-only ingestion telemetry. Counts never come from a truncated UI page."""
from datetime import datetime, timezone, timedelta, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import text
from modules.shared.integration import database_engine


def ingestion_summary(timezone_name='UTC'):
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, 'Unknown timezone') from None
    now = datetime.now(timezone.utc)
    start = datetime.combine(now.astimezone(zone).date(), time.min, tzinfo=zone).astimezone(timezone.utc)
    with database_engine('ingestion').connect() as c:
        result = dict(c.execute(text('''SELECT
            count(*) FILTER (WHERE outcome IN ('success','duplicate') AND completed_at >= :start AND completed_at <= :now) validated_today,
            count(*) FILTER (WHERE outcome='duplicate') duplicates,
            coalesce(sum(bytes_processed) FILTER (WHERE completed_at >= :recent AND completed_at <= :now),0) recent_bytes
            FROM ingestion_run_items'''), {'start':start,'now':now,'recent':now-timedelta(seconds=60)}).mappings().one())
        result['active_runs'] = c.scalar(text("SELECT count(*) FROM ingestion_runs WHERE status IN ('queued','enumerating','processing')"))
    result.update(recent_mib_per_second=round(float(result.pop('recent_bytes'))/1024**2/60,3),
                  window_seconds=60, timezone=timezone_name, day_start=start.isoformat(), measured_at=now.isoformat())
    return result


def run_pipeline(run_id: UUID):
    with database_engine('ingestion').connect() as c:
        if not c.scalar(text('SELECT 1 FROM ingestion_runs WHERE id=:id'),{'id':str(run_id)}):
            raise HTTPException(404,'Ingestion run not found')
        rows = c.execute(text('''SELECT ids.document_id, t.status, t.current_stage, t.stage_results,
            t.error_message, f.embedding_status, f.published
            FROM (SELECT DISTINCT document_id FROM ingestion_run_items
                  WHERE run_id=:id AND document_id IS NOT NULL) ids
            LEFT JOIN enrichment.enrichment_tasks t ON t.document_id=ids.document_id
            LEFT JOIN search.file_metadata f ON f.file_id=ids.document_id::text'''), {'id':str(run_id)}).mappings().all()
    statuses, extraction = {}, {}
    errors = []
    for row in rows:
        status = row['status'] or 'awaiting_delivery'
        statuses[status] = statuses.get(status,0)+1
        stage = (row['stage_results'] or {}).get('ocr_extraction',{}).get('status') or 'pending'
        extraction[stage] = extraction.get(stage,0)+1
        if row['error_message'] and len(errors)<10:
            errors.append({'document_id':str(row['document_id']),'status':status,'message':row['error_message']})
    return {'canonical_documents':len(rows),'ai_statuses':statuses,'extraction':extraction,
            'indexed':sum(r['embedding_status']=='INDEXED' for r in rows),
            'published':sum(bool(r['published']) for r in rows),'errors':errors,
            'measured_at':datetime.now(timezone.utc).isoformat(),
            'scope':'Latest persisted state of distinct canonical documents linked to this run; reused documents may have been enriched earlier. Index counts are persisted Search records, not a live Qdrant health check.'}
