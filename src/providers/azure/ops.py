"""CRUD operations mixin for Microsoft Azure Key Vault provider."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
    ServiceResponseError,
)
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers.azure.helpers import (
    parse_azure_secret_item,
    parse_azure_version_item,
)
from src.providers.errors import (
    CONFLICT,
    CONNECT_TIMEOUT,
    MISSING,
    OTHER,
    READ_TIMEOUT,
    RETRIES,
    guard_network,
    provider_error,
    status_failure,
)

if TYPE_CHECKING:
    pass

NETWORK_ERRORS = (ServiceRequestError, ServiceResponseError)
AZURE_METHODS = (
    "update_metadata",
    "list_secrets",
    "list_versions",
    "access_secret_payload",
    "create_secret",
    "add_secret_version",
    "_set_version_enabled",
    "delete_secret",
)


@guard_network("azure", "Azure Key Vault", NETWORK_ERRORS, *AZURE_METHODS)
class AzureOperationsMixin:
    """Provides client initialization, secret listing, CRUD, and payload access for Azure."""

    @property
    def vault_name(self) -> Optional[str]: ...

    @property
    def vault_url(self) -> Optional[str]: ...

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

        self._client = sc_cls(
            vault_url=url,
            credential=self._credential,
            connection_timeout=CONNECT_TIMEOUT,
            read_timeout=READ_TIMEOUT,
            retry_total=RETRIES,
        )
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
            raise provider_error(
                OTHER,
                _(
                    "Azure authentication error.\n"
                    "Log in with the Azure CLI by running:\n"
                    "  az login\n"
                    "or set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and AZURE_TENANT_ID environment variables."
                ),
                "azure",
                exc,
            ) from exc
        except HttpResponseError as exc:
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=_(
                    "Permission denied accessing Azure Key Vault '{vault}'.\n"
                    "Verify that your account has the 'Key Vault Secrets User' / 'Key Vault Secrets Officer' RBAC role "
                    "or an assigned Access Policy."
                ).format(vault=self.vault_name),
                missing=_("The Azure Key Vault '{vault}' does not exist or was not found.").format(
                    vault=self.vault_name
                ),
                other=_("Azure Key Vault error"),
            ) from exc
        except NETWORK_ERRORS:
            raise  # reported by the guard_network decorator
        except Exception as exc:
            raise provider_error(
                OTHER, f"{_('Error querying Azure Key Vault secrets')}: {exc}", "azure", exc
            ) from exc

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
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=_("Permission denied while listing versions in Azure"),
                other=_("Error listing versions"),
            ) from exc

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
            raise provider_error(
                MISSING,
                _("The secret '{secret}' does not exist in Azure Key Vault.").format(
                    secret=actual_name
                ),
                "azure",
                exc,
            ) from exc
        except HttpResponseError as exc:
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=_(
                    "Permission denied to read secret value for '{secret}'.\n"
                    "Requires 'secrets/get' permission or 'Key Vault Secrets User' role."
                ).format(secret=actual_name),
                other=_("Error accessing secret"),
            ) from exc

    def create_secret(
        self,
        secret_id: str,
        payload_data: Optional[str] = None,
        labels: Optional[dict] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        """Create a secret in Azure Key Vault, refusing to overwrite an existing one."""
        client = self._get_client()
        val = payload_data if payload_data is not None else ""
        tags = {k: str(v) for k, v in labels.items()} if labels else {}

        try:
            client.get_secret(name=secret_id)
        except ResourceNotFoundError:
            pass
        except HttpResponseError:
            pass  # cannot tell (e.g. no "get" permission): let set_secret decide
        else:
            raise provider_error(
                CONFLICT,
                _("The secret '{secret}' already exists. Use 'New Version' to modify it.").format(
                    secret=secret_id
                ),
                "azure",
            )

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
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=_("Permission denied to create secrets in Azure Key Vault"),
                other=_("Error creating secret in Azure"),
            ) from exc

    def update_metadata(
        self, secret_name: str, labels: Dict[str, str], description: Optional[str]
    ) -> None:
        """Replace the tags and the content type (shown as description) of a secret."""
        client = self._get_client()
        name = secret_name.split("/")[-1].split("@")[0]
        try:
            client.update_secret_properties(
                name=name, tags=dict(labels), content_type=description or None
            )
        except HttpResponseError as exc:
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=_("Permission denied to edit the secret"),
                other=_("Error editing secret"),
            ) from exc

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
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=_("Permission denied to add version"),
                other=_("Error adding version in Azure"),
            ) from exc

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
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=lambda message: _(
                    "Permission denied to {action} version in Azure: {message}"
                ).format(action=action_str, message=message),
                other=lambda message: _(
                    "Error while trying to {action} version in Azure: {message}"
                ).format(action=action_str, message=message),
            ) from exc

    def delete_secret(self, secret_name: str) -> None:
        """Delete a secret in Azure Key Vault."""
        client = self._get_client()
        actual_name = secret_name.split("/")[-1].split("@")[0]

        try:
            client.begin_delete_secret(actual_name)
        except HttpResponseError as exc:
            raise status_failure(
                exc,
                "azure",
                status=exc.status_code,
                detail=exc.message,
                denied=_("Permission denied to delete secret in Azure"),
                other=_("Error deleting secret in Azure"),
            ) from exc
