"""CRUD operations mixin for Microsoft Azure Key Vault provider."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers.azure.helpers import (
    parse_azure_secret_item,
    parse_azure_version_item,
)

if TYPE_CHECKING:
    pass


class AzureOperationsMixin:
    """Provides client initialization, secret listing, CRUD, and payload access for Azure."""

    vault_name: Optional[str]
    vault_url: Optional[str]
    _client: Optional[SecretClient]
    _credential: Any

    def _get_client(self) -> SecretClient:
        """Initialize or return cached Azure SecretClient instance."""
        if self._client is not None:
            return self._client

        url = self.vault_url
        if not url:
            raise ValueError(
                _(
                    "No Azure Key Vault configured.\n"
                    "Use the vault switcher button to enter your Key Vault name or set the AZURE_KEYVAULT_NAME environment variable."
                )
            )

        import sys

        az_mod = sys.modules.get("src.providers.azure")
        cred_cls = getattr(az_mod, "DefaultAzureCredential", DefaultAzureCredential)
        sc_cls = getattr(az_mod, "SecretClient", SecretClient)

        if self._credential is None:
            self._credential = cred_cls()

        self._client = sc_cls(vault_url=url, credential=self._credential)
        return self._client

    def list_secrets(self) -> List[SecretItem]:
        """List all secrets in the configured Azure Key Vault."""
        client = self._get_client()
        secrets: List[SecretItem] = []

        try:
            for prop in client.list_properties_of_secrets():
                secrets.append(parse_azure_secret_item(prop, self.vault_url))

            secrets.sort(key=lambda s: s.secret_id.lower())
            return secrets

        except ClientAuthenticationError as exc:
            raise RuntimeError(
                _(
                    "Azure authentication error.\n"
                    "Log in with the Azure CLI by running:\n"
                    "  az login\n"
                    "or set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_TENANT_ID environment variables."
                )
            ) from exc
        except HttpResponseError as exc:
            if exc.status_code == 403:
                raise PermissionError(
                    _(
                        "Permission denied accessing Azure Key Vault '{vault}'.\n"
                        "Verify that your account has the 'Key Vault Secrets User' / 'Key Vault Secrets Officer' RBAC role "
                        "or an assigned Access Policy."
                    ).format(vault=self.vault_name)
                ) from exc
            elif exc.status_code == 404:
                raise FileNotFoundError(
                    _("The Azure Key Vault '{vault}' does not exist or was not found.").format(
                        vault=self.vault_name
                    )
                ) from exc
            raise RuntimeError(f"{_('Azure Key Vault error')}: {exc.message}") from exc
        except Exception as exc:
            raise RuntimeError(f"{_('Error querying Azure Key Vault secrets')}: {exc}") from exc

    def list_versions(self, secret_name: str) -> List[SecretVersionItem]:
        """List all versions of an Azure Key Vault secret."""
        client = self._get_client()
        actual_name = secret_name.split("/")[-1].split("@")[0]
        versions: List[SecretVersionItem] = []

        try:
            for prop in client.list_properties_of_secret_versions(actual_name):
                versions.append(parse_azure_version_item(prop, actual_name))

            def sort_key(v: SecretVersionItem):
                return v.create_time.timestamp() if v.create_time else 0

            versions.sort(key=sort_key, reverse=True)
            return versions

        except HttpResponseError as exc:
            if exc.status_code == 403:
                raise PermissionError(
                    f"{_('Permission denied while listing versions in Azure')}: {exc.message}"
                ) from exc
            raise RuntimeError(f"{_('Error listing versions')}: {exc.message}") from exc

    def access_secret_payload(
        self, secret_name: str, version: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Fetch the value of an Azure Key Vault secret."""
        client = self._get_client()
        actual_name = secret_name.split("/")[-1]
        ver_id = version

        if "@" in actual_name:
            actual_name, ver_part = actual_name.split("@", 1)
            if not ver_id:
                ver_id = ver_part

        try:
            secret = client.get_secret(name=actual_name, version=ver_id)
            val = secret.value or ""
            return val, False

        except ResourceNotFoundError as exc:
            raise FileNotFoundError(
                _("The secret '{secret}' does not exist in Azure Key Vault.").format(
                    secret=actual_name
                )
            ) from exc
        except HttpResponseError as exc:
            if exc.status_code == 403:
                raise PermissionError(
                    _(
                        "Permission denied to read secret value for '{secret}'.\n"
                        "Requires 'secrets/get' permission or 'Key Vault Secrets User' role."
                    ).format(secret=actual_name)
                ) from exc
            raise RuntimeError(f"{_('Error accessing secret')}: {exc.message}") from exc

    def create_secret(
        self,
        secret_id: str,
        payload_data: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[dict] = None,
    ) -> SecretItem:
        """Create or update a secret in Azure Key Vault."""
        client = self._get_client()
        val = payload_data if payload_data is not None else ""
        tags = {k: str(v) for k, v in labels.items()} if labels else {}

        try:
            secret = client.set_secret(
                name=secret_id,
                value=val,
                tags=tags,
                content_type=description,
            )

            return SecretItem(
                name=secret.id or f"{self.vault_url}secrets/{secret_id}",
                secret_id=secret_id,
                provider="azure",
                description=description,
                create_time=datetime.now(),
                labels=tags,
                replication_type="AUTOMATIC",
                locations=[],
            )
        except HttpResponseError as exc:
            if exc.status_code == 403:
                raise PermissionError(
                    f"{_('Permission denied to create secrets in Azure Key Vault')}: {exc.message}"
                ) from exc
            raise RuntimeError(f"{_('Error creating secret in Azure')}: {exc.message}") from exc

    def add_secret_version(self, secret_name: str, payload_data: str) -> SecretVersionItem:
        """Add a new version to an existing Azure secret."""
        client = self._get_client()
        actual_name = secret_name.split("/")[-1].split("@")[0]

        try:
            secret = client.set_secret(name=actual_name, value=payload_data)
            vid = secret.properties.version or ""

            return SecretVersionItem(
                version_id=vid,
                name=f"{actual_name}@{vid}",
                state="ENABLED",
                stages=[],
                create_time=datetime.now(),
                destroy_time=None,
            )
        except HttpResponseError as exc:
            if exc.status_code == 403:
                raise PermissionError(
                    f"{_('Permission denied to add version')}: {exc.message}"
                ) from exc
            raise RuntimeError(f"{_('Error adding version in Azure')}: {exc.message}") from exc

    def enable_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Enables a specific version in Azure Key Vault."""
        return self._set_version_enabled(version_full_name, True)

    def disable_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Disables a specific version in Azure Key Vault."""
        return self._set_version_enabled(version_full_name, False)

    def _set_version_enabled(self, version_full_name: str, enabled: bool) -> SecretVersionItem:
        """Update the enabled status of an Azure Key Vault secret version."""
        client = self._get_client()
        actual_name = version_full_name.split("/")[-1]
        ver_id = None
        if "@" in actual_name:
            actual_name, ver_id = actual_name.split("@", 1)

        try:
            prop = client.update_secret_properties(
                name=actual_name, version=ver_id, enabled=enabled
            )
            vid = prop.version or ver_id or ""
            return SecretVersionItem(
                version_id=vid,
                name=f"{actual_name}@{vid}",
                state="ENABLED" if prop.enabled else "DISABLED",
                stages=[],
                create_time=prop.created_on,
                destroy_time=None,
            )
        except HttpResponseError as exc:
            action_str = _("enable") if enabled else _("disable")
            if exc.status_code == 403:
                raise PermissionError(
                    _("Permission denied to {action} version in Azure: {message}").format(
                        action=action_str, message=exc.message
                    )
                ) from exc
            raise RuntimeError(
                _("Error while trying to {action} version in Azure: {message}").format(
                    action=action_str, message=exc.message
                )
            ) from exc

    def delete_secret(self, secret_name: str) -> None:
        """Delete a secret in Azure Key Vault."""
        client = self._get_client()
        actual_name = secret_name.split("/")[-1].split("@")[0]

        try:
            client.begin_delete_secret(actual_name)
        except HttpResponseError as exc:
            if exc.status_code == 403:
                raise PermissionError(
                    f"{_('Permission denied to delete secret in Azure')}: {exc.message}"
                ) from exc
            raise RuntimeError(f"{_('Error deleting secret in Azure')}: {exc.message}") from exc
