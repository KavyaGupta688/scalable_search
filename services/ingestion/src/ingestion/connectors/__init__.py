from __future__ import annotations

from ingestion.models.connector import Connector, SourceType
from ingestion.connectors.base import SourceConnector, ConnectorError, TransientConnectorError, PermanentConnectorError
from ingestion.connectors.s3 import S3Connector
from ingestion.connectors.nas_smb import NASConnectorSMB
from ingestion.connectors.nas_nfs import NASConnectorNFS


def _parse_smb_unc_path(mount_path: str) -> tuple[str, str, str]:
    """Return ``(server, share, root_path)`` for an SMB UNC path."""
    normalized = mount_path.strip().replace("/", "\\")
    if not normalized.startswith("\\\\"):
        raise ValueError("SMB mount_path must be a UNC path such as '\\\\server\\share'")

    parts = [part for part in normalized[2:].split("\\") if part]
    if len(parts) < 2:
        raise ValueError("SMB mount_path must include both a server and share name")
    return parts[0], parts[1], "\\".join(parts[2:])


def create_connector(connector: Connector, credentials: dict) -> SourceConnector:
    """
    Factory to instantiate the appropriate connector from a DB model + Vault credentials.

    The connector model stores configuration in individual columns, NOT a generic dict.
    Credentials come from Vault and are passed separately.
    """
    if connector.source_type == SourceType.S3:
        return S3Connector(
            endpoint_url=connector.endpoint_url,
            bucket=connector.bucket,
            access_key=credentials.get("access_key", ""),
            secret_key=credentials.get("secret_key", ""),
            auth_mode=connector.s3_auth_mode or "static_keys",
            role_arn=connector.s3_role_arn,
            external_id=credentials.get("external_id") or None,
            session_duration_seconds=connector.s3_session_duration_seconds or 3600,
            addressing_style=connector.addressing_style or "path",
            signature_version=connector.signature_version or "s3v4",
            connector_id=connector.id,
            prefix=connector.s3_prefix or "",
            max_objects=connector.enumeration_max_objects,
            page_size=connector.enumeration_page_size or 1000,
        )
    elif connector.source_type == SourceType.NAS_SMB:
        server, share_name, root_path = _parse_smb_unc_path(connector.mount_path or "")
        return NASConnectorSMB(
            server=server,
            share_name=share_name,
            root_path=root_path,
            username=credentials.get("username", ""),
            password=credentials.get("password", ""),
            domain=credentials.get("domain"),
            connector_id=connector.id,
            max_files=connector.enumeration_max_objects,
        )
    elif connector.source_type == SourceType.NAS_NFS:
        return NASConnectorNFS(
            mount_path=connector.mount_path or "",
            connector_id=connector.id,
            max_files=connector.enumeration_max_objects,
        )
    else:
        raise ValueError(f"Unsupported connector source_type: {connector.source_type}")


__all__ = [
    "SourceConnector",
    "S3Connector",
    "NASConnectorSMB",
    "NASConnectorNFS",
    "ConnectorError",
    "TransientConnectorError",
    "PermanentConnectorError",
    "create_connector",
]
