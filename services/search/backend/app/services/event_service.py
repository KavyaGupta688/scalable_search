from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.file_repository import FileRepository
from app.repositories.dataset_repository import DatasetRepository
from app.clients.audit_client import AuditClient
from app.schemas.events import (
    SearchEventCreate,
    SearchEventResponse,
    DownloadExportRequest,
    DownloadExportResponse,
)
from app.clients.download_client import DownloadClient
from app.utils.query_normalizer import normalize_query_for_trending

logger = logging.getLogger(__name__)


class EventService:
    def __init__(
        self,
        analytics_repo: AnalyticsRepository,
        file_repo: FileRepository,
        dataset_repo: DatasetRepository,
        audit_client: AuditClient,
        download_client: DownloadClient,
    ):
        self.analytics_repo = analytics_repo
        self.file_repo = file_repo
        self.dataset_repo = dataset_repo
        self.audit_client = audit_client
        self.download_client = download_client

    async def record_search_event(
        self,
        event_data: SearchEventCreate,
        user_id: str = "usr_guest_demo",
        user_role: str = "ANALYST",
    ) -> SearchEventResponse:
        from fastapi import HTTPException

        if event_data.file_id and not await self.file_repo.get_by_id(
            event_data.file_id
        ):
            raise HTTPException(404, "File is not available")
        if event_data.dataset_id and not await self.dataset_repo.get_by_id(
            event_data.dataset_id
        ):
            raise HTTPException(404, "Dataset is not available")
        norm_q = (
            normalize_query_for_trending(event_data.query) if event_data.query else None
        )

        event = await self.analytics_repo.log_event(
            event_type=event_data.event_type,
            user_id=user_id,
            user_role=user_role,
            file_id=event_data.file_id,
            dataset_id=event_data.dataset_id,
            query=event_data.query,
            normalized_query=norm_q,
            filters=event_data.filters,
            result_count=event_data.result_count or 0,
            meta_info=event_data.meta_info,
        )

        # Update entity metrics
        if event_data.event_type == "FILE_PREVIEW" and event_data.file_id:
            await self.file_repo.increment_preview_count(event_data.file_id)
        elif event_data.event_type == "DATASET_OPEN" and event_data.dataset_id:
            await self.dataset_repo.increment_view(event_data.dataset_id)

        return SearchEventResponse(
            event_id=event.id, status="RECORDED", timestamp=event.created_at
        )

    async def handle_download_export(
        self,
        request: DownloadExportRequest,
        user_id: str = "usr_guest_demo",
        user_role: str = "ANALYST",
    ) -> DownloadExportResponse:
        """
        Processes batch download selection and dispatches to Download & Auditing module with metadata.csv bundle.
        """
        from fastapi import HTTPException

        raise HTTPException(410, "Use POST /downloads/batch with canonical file_ids")
