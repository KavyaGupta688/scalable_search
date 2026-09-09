from __future__ import annotations
import hvac
from uuid import UUID
from typing import Dict, Any

from ingestion.config import get_settings
from ingestion.monitoring.logging import get_logger

logger = get_logger(__name__)

class VaultService:
    """Service for interacting with HashiCorp Vault KV v2 engine."""
    
    def __init__(self):
        settings = get_settings().vault
        self.url = settings.url
        self.mount_point = settings.mount_point
        self.auth_method = settings.auth_method
        
        # Initialize client
        self.client = hvac.Client(url=self.url)
        
        if self.auth_method == "token":
            self.client.token = settings.token
        elif self.auth_method == "approle":
            try:
                self.client.auth.approle.login(
                    role_id=settings.role_id,
                    secret_id=settings.secret_id
                )
            except hvac.exceptions.VaultError as e:
                logger.error(f"Failed to authenticate with Vault using AppRole: {e}")
                raise
        else:
            logger.warning(f"Unknown vault auth_method: {self.auth_method}")

    def store_connector_secret(self, connector_id: UUID, credentials: Dict[str, Any]) -> str:
        """Stores credentials in Vault and returns the path."""
        path = f"connectors/{connector_id}"
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=credentials,
                mount_point=self.mount_point
            )
            return path
        except hvac.exceptions.VaultError as e:
            logger.error(f"Failed to store secret for connector {connector_id}: {e}")
            raise

    def get_connector_secret(self, vault_path: str) -> Dict[str, Any]:
        """Retrieves credentials from Vault using the given path."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=vault_path,
                mount_point=self.mount_point
            )
            return response['data']['data']
        except hvac.exceptions.VaultError as e:
            logger.error(f"Failed to read secret at {vault_path}: {e}")
            raise

    def delete_connector_secret(self, vault_path: str) -> None:
        """Deletes credentials from Vault."""
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=vault_path,
                mount_point=self.mount_point
            )
        except hvac.exceptions.VaultError as e:
            logger.error(f"Failed to delete secret at {vault_path}: {e}")
            raise

    def check_health(self) -> bool:
        """Checks if the Vault connection is healthy."""
        try:
            return self.client.sys.is_initialized() and not self.client.sys.is_sealed()
        except Exception as e:
            logger.error(f"Vault health check failed: {e}")
            return False
