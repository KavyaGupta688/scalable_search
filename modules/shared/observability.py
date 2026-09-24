"""Bounded, read-only administrative summaries from authoritative records."""
from datetime import datetime, timezone
import math
from uuid import UUID
from sqlalchemy import text
from fastapi import HTTPException
from modules.shared.integration import database_engine, point_id
from modules.shared.catalog import VISIBLE_SQL


def overview_summary():
    with database_engine("ingestion").connect() as c:
        counts = dict(c.execute(text("SELECT count(*) documents, coalesce(sum(size_bytes),0) bytes FROM documents")).mappings().one())
        counts["sources"] = c.execute(text("SELECT count(*) FROM connectors")).scalar_one()
        counts["ingestion"] = dict(c.execute(text("SELECT status,count(*) FROM ingestion_runs GROUP BY status")).all())
        counts["enrichment"] = dict(c.execute(text("SELECT status,count(*) FROM enrichment.enrichment_tasks GROUP BY status")).all())
        counts["modalities"] = [dict(r) for r in c.execute(text("""
            SELECT CASE WHEN mime_type LIKE 'image/%' THEN 'image'
              WHEN mime_type LIKE 'video/%' THEN 'video' WHEN mime_type LIKE 'audio/%' THEN 'audio'
              WHEN mime_type IN ('text/csv','application/csv','application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') THEN 'tabular'
              ELSE 'document' END modality, count(*) count, sum(size_bytes) bytes
            FROM documents GROUP BY 1 ORDER BY 1""")).mappings()]
        counts["recent"] = [dict(r) for r in c.execute(text("""SELECT file_id, file_name, file_type,
            file_size, dataset_name, description, ingested_at FROM search.file_metadata AS file_metadata
            WHERE """ + VISIBLE_SQL + " ORDER BY ingested_at DESC, file_id LIMIT 3")).mappings()]
        counts["published"] = c.execute(text("SELECT count(*) FROM search.file_metadata AS file_metadata WHERE " + VISIBLE_SQL)).scalar_one()
        counts["confidence"] = c.execute(text("""SELECT avg((confidence_scores->>'aggregate')::float)
            FROM (SELECT DISTINCT ON (document_id) confidence_scores FROM enrichment.document_enrichment_metadata
              ORDER BY document_id, updated_at DESC, id DESC) latest
            WHERE jsonb_typeof(confidence_scores->'aggregate')='number'""")).scalar_one()
        latency = c.execute(text("""SELECT avg(execution_time_ms) mean_ms,
            percentile_cont(0.95) WITHIN GROUP (ORDER BY execution_time_ms) p95_ms, count(*) samples
            FROM audit.audit_events WHERE action='SEARCH' AND execution_time_ms>0
            AND occurred_at >= to_char(now() AT TIME ZONE 'UTC' - interval '24 hours', 'YYYY-MM-DD"T"HH24:MI:SS')""")).mappings().one()
        counts["search_latency"] = dict(latency)
    counts["measured_at"] = datetime.now(timezone.utc).isoformat()
    return counts


def pipeline_summary():
    with database_engine("enrichment").connect() as c:
        tasks = dict(c.execute(text("SELECT status,count(*) FROM enrichment_tasks GROUP BY status")).all())
        stages = [dict(r) for r in c.execute(text("""SELECT step.key stage,
            count(*) FILTER (WHERE step.value->>'status'='completed') completed,
            count(*) FILTER (WHERE step.value->>'status'='failed') failed,
            avg((step.value->>'duration_ms')::float) mean_ms
            FROM enrichment_tasks CROSS JOIN LATERAL json_each(stage_results) step
            WHERE json_typeof(step.value->'duration_ms')='number' GROUP BY step.key""")).mappings()]
        recent = c.execute(text("""SELECT count(*) FROM enrichment_tasks
            WHERE status IN ('completed','partial','needs_review') AND updated_at > now()-interval '1 hour'""")).scalar_one()
    return {"tasks": tasks, "stages": stages, "finished_last_hour": recent,
            "scope": "Latest persisted attempt per document; stage duration includes model loading."}


def document_index(document_id: UUID):
    from modules.shared.vector_store import provision, collection
    did = str(document_id)
    with database_engine("ingestion").connect() as c:
        doc = c.execute(text("SELECT source_ref,mime_type FROM documents WHERE id=:id"), {"id": did}).mappings().first()
        if not doc:
            raise HTTPException(404, "Document not found")
        indexed = c.execute(text("SELECT published,enrichment_status FROM search.file_metadata WHERE file_id=:id"), {"id": did}).mappings().first()
    try:
        q = provision(create=False)
        records = q.retrieve(collection(), ids=[point_id(did)], with_vectors=True, with_payload=False)
        from modules.shared.semantic_index import collection_name
        representations = []
        visual_status = "not_indexed"
        if q.collection_exists(collection_name()):
            semantic = q.retrieve(collection_name(), ids=[point_id(did)], with_vectors=True, with_payload=True)
            if semantic:
                visual_status = semantic[0].payload.get("visual_status", "not_indexed")
                for name, vectors in semantic[0].vector.items():
                    representations.append({"name": name, "count": len(vectors),
                        "dimensions": len(vectors[0]) if vectors else 0})
    except Exception:
        raise HTTPException(503, "Vector index is temporarily unavailable") from None
    vector = records[0].vector if records else None
    if vector is not None and (not isinstance(vector, list) or len(vector) != 512 or not all(math.isfinite(v) for v in vector)):
        raise HTTPException(503, "Stored vector is incompatible with the configured collection")
    return {"document_id": did, "source_ref": doc["source_ref"], "mime_type": doc["mime_type"],
            "indexed": vector is not None, "published": bool(indexed and indexed["published"]),
            "dimensions": len(vector) if vector is not None else None,
            "norm": math.sqrt(sum(v*v for v in vector)) if vector is not None else None,
            "representations": representations, "visual_status": visual_status,
            "vector": vector, "model": "Legacy CLIP ViT-B/32", "measured_at": datetime.now(timezone.utc).isoformat()}
