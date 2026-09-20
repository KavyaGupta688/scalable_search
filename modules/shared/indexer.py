"""Idempotently project canonical ingestion/AI records into Search and Qdrant."""

import json
import os
from pathlib import PurePosixPath
from sqlalchemy import text
from modules.shared.integration import database_engine, point_id
from modules.shared.vector_store import client, collection
from modules.shared.publication import safety_cleared


def index_document(document_id):
    engine = database_engine("search")
    with engine.begin() as conn:
        row = (
            conn.execute(
                text("""SELECT d.*, c.name AS connector_name,
            e.status AS license_status, e.expires_at, e.license_start_at,
            t.status AS task_status, m.*,
            v.title AS vendor_title, v.description AS vendor_description,
            v.primary_category, v.tags AS vendor_tags, v.additional_metadata
            FROM ingestion.documents d
            JOIN ingestion.connectors c ON c.id=d.source_connector_id
            JOIN ingestion.license_entitlements e ON e.id=d.entitlement_id
            JOIN enrichment.enrichment_tasks t ON t.document_id=d.id
            LEFT JOIN LATERAL (SELECT * FROM enrichment.document_enrichment_metadata
                WHERE document_id=d.id ORDER BY updated_at DESC,id LIMIT 1) m ON true
            LEFT JOIN LATERAL (SELECT * FROM ingestion.document_metadata
                WHERE document_id=d.id ORDER BY (source_asset_id=m.source_asset_id) DESC NULLS LAST,source_asset_id LIMIT 1) v ON true
            WHERE d.id=:id"""),
                {"id": document_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise LookupError("Canonical document/task not found")
        row = dict(row)
        safety = row.get("privacy_safety_labels") or {}
        cleared = safety_cleared(safety, float(os.getenv("TOXICITY_THRESHOLD", "0.8")))
        published = row["task_status"] in ("completed", "partial") and cleared
        vendor = {
            "title": row.get("vendor_title"),
            "description": row.get("vendor_description"),
            "tags": row.get("vendor_tags") or [],
            "additional_metadata": row.get("additional_metadata") or {},
        }
        ai_tags = [
            t.get("tag") or t.get("label") if isinstance(t, dict) else str(t)
            for t in row.get("generated_tags") or []
        ]
        tags = list(dict.fromkeys(t for t in [*ai_tags, *vendor["tags"]] if t))
        mime = row["mime_type"]
        file_type = (
            "csv"
            if mime in ("text/csv", "text/tab-separated-values")
            else mime.split("/")[0]
        )
        if file_type not in ("image", "video", "audio", "csv"):
            file_type = "document"
        filename = PurePosixPath(row["source_ref"].replace("\\", "/")).name
        if filename.lower().endswith(".csv"):
            file_type = "csv"
        technical = row.get("additional_metadata") or {}
        values = dict(
            width=technical.get("width"),
            height=technical.get("height"),
            duration=technical.get("duration"),
            file_id=document_id,
            dataset_id=str(row["source_connector_id"]),
            dataset_name=row["connector_name"],
            file_name=filename,
            file_type=file_type,
            mime_type=mime,
            file_size=row["size_bytes"],
            title=row.get("vendor_title") or filename,
            description=row.get("short_description") or row.get("vendor_description"),
            tags=json.dumps(tags),
            category=row.get("primary_category") or "Uncategorized",
            content_summary=row.get("search_description"),
            caption=row.get("long_description"),
            ocr_text=row.get("ocr_text") or row.get("native_document_text"),
            transcript=row.get("transcribed_text"),
            checksum=row["checksum_sha256"],
            source_batch=str(row.get("run_id") or ""),
            ingested_at=row["license_start_at"],
            preview_url=f"/documents/{document_id}/content",
            ai_generated=bool(safety.get("ai_generated_flagged")),
            pii_detected=bool(safety.get("contains_pii")),
            nsfw_detected=bool(safety.get("nsfw_flagged")),
            published=published,
            enrichment_status=row["task_status"],
            vendor_metadata=json.dumps(vendor),
            ai_metadata_version=str(row.get("enrichment_version") or ""),
            embedding_model="ViT-B-32/openai/quickgelu",
            embedding_version="1",
            embedding_status="INDEXED" if published else "PENDING",
        )
        payload = {
            k: v
            for k, v in values.items()
            if k
            in (
                "file_id",
                "dataset_id",
                "file_type",
                "category",
                "ai_generated",
                "pii_detected",
                "published",
                "width",
                "height",
                "duration",
            )
        }
        payload.update(
            document_id=document_id,
            tags=tags,
            expires_at=row["expires_at"].isoformat(),
            ingested_at=row["license_start_at"].isoformat(),
        )
        q = client()
        points = q.retrieve(collection(), ids=[point_id(document_id)])
        if published and not points:
            raise RuntimeError("Enrichment vector is not durable yet")
        if points:
            q.set_payload(
                collection(), payload=payload, points=[point_id(document_id)], wait=True
            )
        conn.execute(
            text("""INSERT INTO datasets(id,name,category,file_count,total_size_bytes,view_count,download_count,search_hit_count,popularity_score,created_at,updated_at)
            VALUES (:id,:name,:category,0,0,0,0,0,0,now(),now()) ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name"""),
            {
                "id": values["dataset_id"],
                "name": values["dataset_name"],
                "category": values["category"],
            },
        )
        columns = list(values)
        expressions = [
            f"CAST(:{k} AS json)" if k in ("tags", "vendor_metadata") else ":" + k
            for k in columns
        ]
        conn.execute(
            text(
                "INSERT INTO file_metadata ("
                + ",".join(columns)
                + ",download_count,file_preview_count) VALUES ("
                + ",".join(expressions)
                + ",0,0) ON CONFLICT (file_id) DO UPDATE SET "
                + ",".join(k + "=EXCLUDED." + k for k in columns if k != "file_id")
            ),
            values,
        )
        conn.execute(
            text("""UPDATE datasets SET file_count=(SELECT count(*) FROM file_metadata WHERE dataset_id=:id AND published),
            total_size_bytes=(SELECT coalesce(sum(file_size),0) FROM file_metadata WHERE dataset_id=:id AND published) WHERE id=:id"""),
            {"id": values["dataset_id"]},
        )
