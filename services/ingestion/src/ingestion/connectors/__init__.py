from __future__ import annotations

from ingestion.models.connector import Connector, SourceType
from ingestion.connectors.base import SourceConnector, ConnectorError, TransientConnectorError, PermanentConnectorError
from ingestion.connectors.s3 import S3Connector
from ingestion.connectors.nas_smb import NASConnectorSMB
from ingestion.connectors.nas_nfs import NASConnectorNFS


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
            addressing_style=connector.addressing_style or "path",
            signature_version=connector.signature_version or "s3v4",
        )
    elif connector.source_type == SourceType.NAS_SMB:
        # NAS SMB: mount_path is "\\server\share" format; extract server and share
        mount_path = connector.mount_path or ""
        # Parse UNC path: \\server\share -> server, share
        parts = mount_path.replace("/", "\\").strip("\\").split("\\", 1)
        server = parts[0] if len(parts) > 0 else ""
        share_name = parts[1] if len(parts) > 1 else ""
        return NASConnectorSMB(
            server=server,
            share_name=share_name,
            username=credentials.get("username", ""),
            password=credentials.get("password", ""),
            domain=credentials.get("domain"),
        )
    elif connector.source_type == SourceType.NAS_NFS:
        return NASConnectorNFS(
            mount_path=connector.mount_path or "",
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
