"""Internal aggregate exporter. No document IDs, secrets or content become labels."""
import asyncio
import json
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from prometheus_client import CollectorRegistry, Gauge, generate_latest, CONTENT_TYPE_LATEST
from sqlalchemy import text
from modules.shared.integration import database_engine
from modules.shared.observability import pipeline_summary

MODEL_NAMES = ('ram','clip','yolo','blip','whisper','paddleocr','presidio','nudenet',
               'bart_mnli','spacy','keybert','summarizer','face_detector','toxicity','ai_generated_detector')
STATE = {"data": None, "error": None}


def read_models():
    path = Path(os.getenv('AI_MODEL_READINESS_FILE', '/models/provisioning/results.json'))
    try:
        data = json.loads(path.read_text())
        return {"checked_at": path.stat().st_mtime, "models": [
            {"name": name, "initialized": data.get(name, {}).get('ready')
             if isinstance(data.get(name, {}).get('ready'), bool) else None} for name in MODEL_NAMES]}
    except (OSError, ValueError):
        return {"checked_at": None, "models": [{"name": name, "initialized": None} for name in MODEL_NAMES]}


def collect():
    data = pipeline_summary()
    with database_engine('ingestion').connect() as c:
        data['documents'] = c.execute(text('SELECT count(*) FROM documents')).scalar_one()
        data['outboxes'] = {schema: c.execute(text(f'SELECT count(*) FROM {schema}.integration_outbox WHERE delivered_at IS NULL')).scalar_one()
                           for schema in ('ingestion','enrichment','search','download')}
        data['downloads'] = dict(c.execute(text('SELECT status,count(*) FROM download.document_download_jobs GROUP BY status')).all())
    def ready(name):
        try:
            return name, httpx.get(f'http://{name}:8000/ready', timeout=4).status_code == 200
        except httpx.HTTPError:
            return name, False
    with ThreadPoolExecutor(max_workers=4) as executor:
        data['services'] = dict(executor.map(ready, ('ingestion','search','ai','download')))
    data.update(read_models())
    data['measured_at'] = time.time()
    return data


async def refresh():
    while True:
        try:
            STATE.update(data=await asyncio.to_thread(collect), error=None)
        except Exception as exc:
            STATE['error'] = type(exc).__name__
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(refresh())
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)


@app.get('/snapshot')
def snapshot():
    data = STATE['data']
    if STATE['error'] or not data or time.time()-data['measured_at'] > 90:
        raise HTTPException(503, 'Monitoring data is temporarily unavailable')
    return data


@app.get('/metrics')
def metrics():
    registry = CollectorRegistry()
    def gauge(name, help_text, value, labels=None):
        metric = Gauge(name, help_text, list((labels or {}).keys()), registry=registry)
        if labels:
            for row, number in value:
                metric.labels(*row).set(number)
        else:
            metric.set(value)
    try:
        data = snapshot()
    except HTTPException:
        data = None
    gauge('platform_collection_success', 'Whether the latest aggregate collection succeeded and is fresh', int(data is not None))
    if data:
        gauge('platform_snapshot_timestamp_seconds', 'Time of the latest successful aggregate collection', data['measured_at'])
        gauge('platform_documents', 'Persisted canonical documents', data['documents'])
        for name, source, label in [('platform_ai_tasks','tasks','status'), ('platform_download_jobs','downloads','status'),
                                     ('platform_outbox_pending','outboxes','module'),('platform_service_ready','services','service')]:
            gauge(name, 'Latest persisted count or readiness', [((k,),v) for k,v in data[source].items()], {label: None})
        gauge('platform_ai_finished_last_hour', 'Documents whose latest terminal attempt finished in the last hour', data['finished_last_hour'])
        gauge('platform_ai_stage_mean_seconds', 'Mean duration of latest recorded attempts, including model loading',
              [((r['stage'],),r['mean_ms']/1000) for r in data['stages'] if r['mean_ms'] is not None], {'stage':None})
        gauge('platform_model_initialized', 'Saved model initialization evidence, not currently loaded runtime status',
              [((r['name'],),int(r['initialized'])) for r in data['models'] if r['initialized'] is not None], {'model':None})
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
