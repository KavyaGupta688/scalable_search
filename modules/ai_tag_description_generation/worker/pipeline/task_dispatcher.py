import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional

from modules.ai_tag_description_generation.app.db import get_sync_session
from modules.ai_tag_description_generation.app.models import EnrichmentTask

logger = logging.getLogger(__name__)

PIPELINE_STAGES = [
    'preprocessing', 
    'ocr_extraction', 
    'tagging', 
    'captioning', 
    'quality_safety', 
    'metadata_fusion', 
    'confidence_validation', 
    'persistence', 
    'event_publication'
]

def dispatch_or_resume(
    file_id: str, 
    storage_path: str, 
    file_type: str, 
    checksum: str, 
    source_metadata: Optional[dict] = None
) -> Tuple[EnrichmentTask, Optional[str]]:
    """
    Determine whether to start a new task, resume an existing one, or skip if completed.
    """
    with get_sync_session() as session:
        task = session.query(EnrichmentTask).filter(EnrichmentTask.file_id == file_id).first()
        
        if task:
            if task.status == 'completed':
                return task, None
            if task.status == 'failed_terminal':
                return task, None
            if task.status in ('in_progress', 'partial', 'needs_review'):
                if task.retry_count < task.max_retries:
                    # Stage outputs include in-memory images/tensors and cannot
                    # safely be reconstructed from the JSON checkpoint. Restart
                    # from preprocessing while keeping prior results as audit data.
                    return task, PIPELINE_STAGES[0]
                else:
                    return task, None
            if task.status == 'queued':
                return task, PIPELINE_STAGES[0]
        else:
            task = EnrichmentTask(
                file_id=file_id,
                storage_path=storage_path,
                file_type=file_type,
                checksum=checksum,
                source_metadata=source_metadata or {},
                status='queued',
                retry_count=0,
                stage_results={}
            )
            session.add(task)
            session.commit()
            return task, PIPELINE_STAGES[0]
            
        return task, None

def acquire_lock(file_id: str, worker_id: str, ttl_seconds: int = 300) -> bool:
    """
    Acquire a distributed lock for the task.
    """
    with get_sync_session() as session:
        task = session.query(EnrichmentTask).filter(EnrichmentTask.file_id == file_id).first()
        if not task:
            return False
            
        now = datetime.now(timezone.utc)
        if task.locked_by == worker_id:
            # Renew lock
            task.lock_expires_at = now + timedelta(seconds=ttl_seconds)
            session.commit()
            return True
            
        if not task.locked_by or (task.lock_expires_at and task.lock_expires_at < now):
            # Acquire lock
            task.locked_by = worker_id
            task.lock_expires_at = now + timedelta(seconds=ttl_seconds)
            session.commit()
            return True
            
        return False

def release_lock(file_id: str, worker_id: str) -> None:
    """
    Release the lock if held by this worker.
    """
    with get_sync_session() as session:
        task = session.query(EnrichmentTask).filter(EnrichmentTask.file_id == file_id).first()
        if task and task.locked_by == worker_id:
            task.locked_by = None
            task.lock_expires_at = None
            session.commit()

def update_stage(
    file_id: str, 
    stage_name: str, 
    status: str, 
    error: Optional[str] = None, 
    duration_ms: Optional[int] = None
) -> None:
    """
    Update the task's stage results and current stage.
    """
    with get_sync_session() as session:
        task = session.query(EnrichmentTask).filter(EnrichmentTask.file_id == file_id).first()
        if not task:
            return
            
        # Ensure stage_results is initialized
        if task.stage_results is None:
            task.stage_results = {}
            
        stage_data = task.stage_results.get(stage_name, {})
        stage_data['status'] = status
        if error:
            stage_data['error'] = error
        if duration_ms is not None:
            stage_data['duration_ms'] = duration_ms
            
        # SQLAlchemy needs explicit reassignment for JSON changes
        # depending on dialect, or use flag_modified
        new_results = dict(task.stage_results)
        new_results[stage_name] = stage_data
        task.stage_results = new_results
        
        task.current_stage = stage_name
        session.commit()

def transition_status(file_id: str, new_status: str, error_message: Optional[str] = None) -> None:
    """
    Update the task status with validation on allowed transitions.
    """
    allowed_transitions = {
        'queued': ['in_progress'],
        'in_progress': ['completed', 'partial', 'needs_review', 'failed_terminal'],
        'partial': ['in_progress'],
        'needs_review': ['in_progress'],
        'failed_terminal': [],
        'completed': []
    }
    
    with get_sync_session() as session:
        task = session.query(EnrichmentTask).filter(EnrichmentTask.file_id == file_id).first()
        if not task:
            return
            
        if new_status in allowed_transitions.get(task.status, []):
            task.status = new_status
            if error_message:
                task.error_message = error_message
            task.updated_at = datetime.now(timezone.utc)
            session.commit()
        else:
            logger.warning(f"Invalid state transition attempted: {task.status} -> {new_status}")
