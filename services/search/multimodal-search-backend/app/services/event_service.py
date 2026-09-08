from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.file_repository import FileRepository
from app.repositories.dataset_repository import DatasetRepository
from app.clients.audit_client import AuditClient
from app.schemas.events import SearchEventCreate, SearchEventResponse, DownloadExportRequest, DownloadExportResponse
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
        download_client: DownloadClient
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
        user_role: str = "ANALYST"
    ) -> SearchEventResponse:
        norm_q = normalize_query_for_trending(event_data.query) if event_data.query else None
        
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
            meta_info=event_data.meta_info
        )

        # Update entity metrics
        if event_data.event_type == "FILE_PREVIEW" and event_data.file_id:
            await self.file_repo.increment_preview_count(event_data.file_id)
        elif event_data.event_type == "DATASET_OPEN" and event_data.dataset_id:
            await self.dataset_repo.increment_view(event_data.dataset_id)

        # Forward critical audit events to downstream Audit module
        if event_data.event_type in ["DOWNLOAD_REQUEST", "SIMILAR_SEARCH", "FILE_PREVIEW"]:
            await self.audit_client.log_audit_event(
                event_type=event_data.event_type,
                user_id=user_id,
                user_role=user_role,
                resource_id=event_data.file_id or event_data.dataset_id,
                details={"query": event_data.query, "meta": event_data.meta_info}
            )

        return SearchEventResponse(
            event_id=event.id,
            status="RECORDED",
            timestamp=event.created_at
        )

    async def handle_download_export(
        self,
        request: DownloadExportRequest,
        user_id: str = "usr_guest_demo",
        user_role: str = "ANALYST"
    ) -> DownloadExportResponse:
        """
        Processes batch download selection and dispatches to Download & Auditing module with metadata.csv bundle.
        """
        # Increment download counts on files
        for fid in request.selected_file_ids:
            await self.file_repo.increment_download_count(fid)
            
        if request.dataset_id:
            await self.dataset_repo.increment_download(request.dataset_id, count=len(request.selected_file_ids))

        # Log audit event
        audit_id = await self.audit_client.log_audit_event(
            event_type="DOWNLOAD_BATCH_SELECTION",
            user_id=user_id,
            user_role=user_role,
            resource_id=request.dataset_id or "multi_files",
            details={
                "file_count": len(request.selected_file_ids),
                "file_ids": request.selected_file_ids[:10],
                "search_query": request.search_query,
                "filters": request.applied_filters,
                "bundle_metadata_csv": request.bundle_metadata_csv
            }
        )

        # Dispatch to download client
        dispatch_res = await self.download_client.dispatch_download_request(
            selected_file_ids=request.selected_file_ids,
            user_id=user_id,
            user_role=user_role,
            bundle_metadata_csv=request.bundle_metadata_csv,
            search_query=request.search_query,
            applied_filters=request.applied_filters
        )

        return DownloadExportResponse(
            export_task_id=dispatch_res["task_id"],
            status="SUBMITTED_TO_DOWNLOAD_AUDIT",
            total_files=len(request.selected_file_ids),
            selected_file_ids=request.selected_file_ids,
            metadata_bundle="metadata.csv",
            audit_event_id=audit_id,
            estimated_archive_size_bytes=dispatch_res["estimated_archive_size_bytes"],
            message="Batch selection successfully submitted to Download and Auditing Module."
        )
