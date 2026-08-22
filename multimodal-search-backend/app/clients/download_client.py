import logging
from typing import List, Dict, Any
import uuid

logger = logging.getLogger(__name__)

class DownloadClient:
    """
    Sends selected files and download manifests to Download & Auditing module.
    """
    async def dispatch_download_request(
        self,
        selected_file_ids: List[str],
        user_id: str,
        user_role: str,
        bundle_metadata_csv: bool,
        search_query: str | None,
        applied_filters: Dict[str, Any] | None
    ) -> Dict[str, Any]:
        task_id = f"dl_task_{uuid.uuid4().hex[:10]}"
        logger.info(
            f"[DOWNLOAD DISPATCH] Created task {task_id} for {len(selected_file_ids)} files. "
            f"User: {user_id}. Bundle CSV: {bundle_metadata_csv}"
        )
        return {
            "task_id": task_id,
            "status": "QUEUED_FOR_PACKAGING",
            "file_count": len(selected_file_ids),
            "estimated_archive_size_bytes": len(selected_file_ids) * 1024 * 1024 * 5  # approx 5MB/file
        }

_download_client = DownloadClient()

def get_download_client() -> DownloadClient:
    return _download_client
