import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)

class AuditClient:
    """
    Sends auditing events to downstream Download & Auditing module.
    """
    async def log_audit_event(
        self,
        event_type: str,
        user_id: str,
        user_role: str,
        resource_id: str | None,
        details: Dict[str, Any]
    ) -> str:
        audit_id = f"aud_{uuid.uuid4().hex[:12]}"
        logger.info(
            f"[AUDIT LOG {audit_id}] Type: {event_type} | User: {user_id} ({user_role}) | "
            f"Resource: {resource_id} | Details: {details}"
        )
        return audit_id

_audit_client = AuditClient()

def get_audit_client() -> AuditClient:
    return _audit_client
