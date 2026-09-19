"""Administrator audit queries and signed service event ingestion."""

import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from modules.shared.auth.dependencies import require_admin
from modules.shared.integration import internal_user
from modules.shared.audit import list_persisted, record

router = APIRouter()


class Event(BaseModel):
    event_id: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=80)
    actor: str
    entity_type: str
    entity_id: str
    user_role: str = "service"
    status: str = "SUCCESS"
    correlation_id: str | None = None
    metadata: dict = Field(default_factory=dict)


@router.post("/internal/audit/events")
def service_event(
    event: Event, identity=Depends(internal_user("audit", "audit:write"))
):
    return record(**event.model_dump())


@router.get("/api/audit/logs")
@router.get("/downloads/audit/events")
def events(
    action: str | None = None,
    actor: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    user=Depends(require_admin),
):
    # SQL pagination is applied in the store, never in the browser.
    from sqlalchemy import text
    from modules.shared.audit import _engine

    conditions = " WHERE 1=1"
    params = {"limit": page_size, "offset": (page - 1) * page_size}
    for key, value in (("action", action), ("actor", actor), ("status", status)):
        if value:
            conditions += f" AND {key}=:{key}"
            params[key] = value
    with _engine().connect() as conn:
        total = conn.execute(
            text("SELECT count(*) FROM audit_events" + conditions), params
        ).scalar_one()
        rows = conn.execute(
            text(
                "SELECT * FROM audit_events"
                + conditions
                + " ORDER BY occurred_at DESC,event_id LIMIT :limit OFFSET :offset"
            ),
            params,
        ).mappings()
        import json

        result = [
            {
                **dict(r),
                "metadata": json.loads(r["metadata_json"]),
                "query": r["query_text"],
            }
            for r in rows
        ]
    return {"events": result, "total": total, "page": page, "page_size": page_size}


@router.get("/downloads/audit/export.csv")
def export(user=Depends(require_admin)):
    def rows():
        page = 1
        columns = [
            "event_id",
            "action",
            "actor",
            "status",
            "entity_type",
            "entity_id",
            "occurred_at",
            "correlation_id",
        ]
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(columns)
        yield buffer.getvalue()
        while True:
            batch = events(page=page, page_size=500, user=user)["events"]
            if not batch:
                break
            buffer.seek(0)
            buffer.truncate(0)
            for row in batch:
                values = [str(row.get(k) or "") for k in columns]
                writer.writerow(
                    [
                        "'" + v if v.startswith(("=", "+", "-", "@")) else v
                        for v in values
                    ]
                )
            yield buffer.getvalue()
            page += 1

    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit.csv"},
    )


@router.get("/admin/audit/analytics")
def analytics(hours: int = Query(24, ge=1, le=720), user=Depends(require_admin)):
    from sqlalchemy import text
    from modules.shared.audit import _engine

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT action,status,count(*) AS count FROM audit_events WHERE occurred_at>=:cutoff GROUP BY action,status"
                ),
                {"cutoff": cutoff},
            )
            .mappings()
            .all()
        )
    return {
        "hours": hours,
        "total": sum(r["count"] for r in rows),
        "breakdown": [dict(r) for r in rows],
    }
