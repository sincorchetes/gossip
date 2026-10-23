"""Microsoft Azure Key Vault secret provider implementation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Callable, List, Optional, Tuple

from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.i18n import _
from src.models import AzureVaultItem, SecretItem, SecretVersionItem
from src.providers.base import BaseSecretProvider


class AzureSecretClient(BaseSecretProvider):
    """Provider implementation for Azure Key Vault."""

    def __init__(self, vault_name: Optional[str] = None):
        """Initialize the Azure Key Vault client.

        Args:
            vault_name: Optional Key Vault name or URI. If omitted, attempts autodetection.
        """
        self._vault_name = vault_name or self.detect_vault_name()
        self._credential = None
        self._client: Optional[SecretClient] = None

    @property
    def provider_id(self) -> str:
        """Return the unique provider identifier string ('azure')."""
        return "azure"

    @property
    def provider(self) -> str:
        """Return the provider identifier string (alias for provider_id)."""
        return "azure"

    @property
    def display_name(self) -> str:
        """Return the human-readable provider name shown in the UI switcher."""
        return "Microsoft Azure (Key Vault)"

    @property
    def icon_name(self) -> str:
        """Return the FreeDesktop symbolic icon name for the context switcher button."""
        return "security-high-symbolic"

    @property
    def context_title(self) -> str:
        """Return the localized context title for dialog headers."""
        return _("Azure Key Vault")

    @property
    def context_subtitle(self) -> str:
        """Return the localized subtitle with active Azure Key Vault name."""
        return _("Azure Vault: %s") % (self.vault_name or _("No vault selected"))

    @property
    def context_btn_tooltip(self) -> str:
        """Return the localized tooltip for the vault switcher button."""
        return _("Switch Azure Key Vault")

    @property
    def loading_message(self) -> str:
        """Return the localized message shown while querying Azure Key Vault."""
        return _("Querying Azure Key Vault...")

    @property
    def empty_message(self) -> str:
        """Return the localized message shown when no secrets exist in this Azure Key Vault."""
        return _("No secrets found in this Azure Key Vault.")

    @property
    def error_message(self) -> str:
        """Return the localized message shown when connection or query fails."""
        return _("Could not connect to Azure.")

    @property
    def supports_version_toggling(self) -> bool:
        """Return True indicating Azure Key Vault supports enabling/disabling versions."""
        return True

    @property
    def supports_version_destroy(self) -> bool:
        """Return False indicating Azure Key Vault does not support single-version payload purge."""
        return False

    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        """Open the modal dialog to select or configure an Azure Key Vault.

        Args:
            parent_window: GTK parent window to transient the dialog for.
            on_success: Callback function invoked after vault change.
        """
        from src.ui.dialogs import show_change_azure_vault_dialog

        def on_confirm(vault_name: str) -> None:
            """Update active Azure Key Vault name and invoke completion callback."""
            self.vault_name = vault_name
            on_success()

        show_change_azure_vault_dialog(parent_window, self, on_confirm)

    def toggle_version_state(self, version: str | SecretVersionItem, enable: bool) -> None:
        """Enable or disable a specific Azure Key Vault secret version.

        Args:
            version: SecretVersionItem or version identifier string.
            enable: True to enable, False to disable.
        """
        name = version.name if isinstance(version, SecretVersionItem) else version
        self._set_version_enabled(name, enable)

    @property
    def vault_name(self) -> Optional[str]:
        """Return the active Azure Key Vault name or short identifier."""
        if not self._vault_name:
            self._vault_name = self.detect_vault_name()
        return self._vault_name

    @vault_name.setter
    def vault_name(self, val: Optional[str]) -> None:
        """Set active Azure Key Vault name and reset client instance."""
        new_val = val.strip() if val else None
        if new_val != self._vault_name:
            self._vault_name = new_val
            self._client = None

    @property
    def vault_url(self) -> Optional[str]:
        """Return the full HTTPS vault endpoint URL (e.g. 'https://my-vault.vault.azure.net/')."""
        if not self.vault_name:
            return None
        v = self.vault_name.strip()
        if v.startswith("http://") or v.startswith("https://"):
            return v if v.endswith("/") else f"{v}/"
        return f"https://{v}.vault.azure.net/"

    @classmethod
    def detect_vault_name(cls) -> Optional[str]:
        """Detect active Azure Key Vault name from environment variables.

        Returns:
            Optional[str]: Detected vault identifier or None.
        """
        for var in ("AZURE_KEYVAULT_NAME", "AZURE_VAULT_NAME", "AZURE_VAULT_URL", "KEYVAULT_NAME"):
            val = os.getenv(var)
            if val and val.strip():
                clean = val.strip()
                if "vault.azure.net" in clean:
                    clean = clean.replace("https://", "").replace("http://", "").split(".")[0]
                return clean
        return None

    def list_available_vaults(self) -> List[AzureVaultItem]:
        """List accessible Azure Key Vaults discovered via Azure CLI.

        Returns:
            List[AzureVaultItem]: List of discovered vault items.
        """
        vaults: List[AzureVaultItem] = []
        try:
            cmd = "az.cmd" if sys.platform == "win32" else "az"
            res = subprocess.run(
                [
                    cmd,
                    "keyvault",
                    "list",
                    "--query",
                    "[].{name: name, vaultUri: properties.vaultUri, location: location}",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
                shell=(sys.platform == "win32"),
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout.strip())
                for item in data:
                    name = item.get("name", "")
                    uri = item.get("vaultUri", f"https://{name}.vault.azure.net/")
                    loc = item.get("location")
                    if name:
                        vaults.append(AzureVaultItem(name=name, vault_uri=uri, location=loc))
        except Exception:
            pass

        # If current vault is not in list, add it
        current = self.vault_name
        if current and not any(v.name.lower() == current.lower() for v in vaults):
            vaults.insert(
                0,
                AzureVaultItem(
                    name=current, vault_uri=self.vault_url or f"https://{current}.vault.azure.net/"
                ),
            )

        vaults.sort(key=lambda v: v.name.lower())
        return vaults

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

        if self._credential is None:
            self._credential = DefaultAzureCredential()

        self._client = SecretClient(vault_url=url, credential=self._credential)
        return self._client

    def list_secrets(self) -> List[SecretItem]:
        """List all secrets in the configured Azure Key Vault.

        Returns:
            List[SecretItem]: List of normalized secret item instances.

        Raises:
            RuntimeError: If Azure authentication fails or vault query errors out.
            PermissionError: If caller lacks Key Vault Secrets User/Officer role.
            FileNotFoundError: If the Key Vault does not exist.
        """
        client = self._get_client()
        secrets: List[SecretItem] = []

        try:
            for prop in client.list_properties_of_secrets():
                sec_id = prop.name
                tags_dict = dict(prop.tags) if prop.tags else {}
                content_type = prop.content_type

                secrets.append(
                    SecretItem(
                        name=prop.id or f"{self.vault_url}secrets/{sec_id}",
                        secret_id=sec_id,
                        provider="azure",
                        description=content_type,
                        create_time=prop.created_on,
                        last_changed_date=prop.updated_on,
                        labels=tags_dict,
                        replication_type="AUTOMATIC",
                        locations=[],
                    )
                )

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
        """List all versions of an Azure Key Vault secret.

        Args:
            secret_name: Name or URI of the secret.

        Returns:
            List[SecretVersionItem]: Chronologically ordered secret versions.

        Raises:
            PermissionError: If access is denied.
            RuntimeError: If listing versions fails.
        """
        client = self._get_client()
        actual_name = secret_name.split("/")[-1].split("@")[0]
        versions: List[SecretVersionItem] = []

        try:
            for prop in client.list_properties_of_secret_versions(actual_name):
                vid = prop.version or ""
                state_str = "ENABLED" if prop.enabled else "DISABLED"

                versions.append(
                    SecretVersionItem(
                        version_id=vid,
                        name=f"{actual_name}@{vid}",
                        state=state_str,
                        stages=[],
                        create_time=prop.created_on,
                        destroy_time=None,
                    )
                )

            # Sort descending by creation date
            def sort_key(v: SecretVersionItem):
                """Extract timestamp for sorting versions in descending order."""
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
        """Fetch the value of an Azure Key Vault secret.

        Args:
            secret_name: Identifier of the target secret.
            version: Optional version identifier string.

        Returns:
            Tuple[str, bool]: Secret payload string and is_binary boolean flag.

        Raises:
            FileNotFoundError: If the secret does not exist.
            PermissionError: If caller lacks Key Vault secret get permissions.
            RuntimeError: If access fails.
        """
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
        """Create or update a secret in Azure Key Vault.

        Args:
            secret_id: Key Vault secret identifier.
            payload_data: String value to store.
            description: Optional content-type or description.
            labels: Optional dictionary of tags.

        Returns:
            SecretItem: Newly created secret metadata.

        Raises:
            PermissionError: If caller lacks Key Vault set secret permission.
            RuntimeError: If creation fails.
        """
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
        """Add a new version to an existing Azure secret.

        Args:
            secret_name: Name or URI of the target secret.
            payload_data: New string value to store.

        Returns:
            SecretVersionItem: Newly created secret version item.

        Raises:
            PermissionError: If caller lacks permissions to set secret.
            RuntimeError: If version creation fails.
        """
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
        """Update the enabled status of an Azure Key Vault secret version.

        Args:
            version_full_name: Compound identifier in the form 'name@version_id'.
            enabled: True to enable the version, False to disable it.

        Returns:
            Updated SecretVersionItem instance reflecting the new state.

        Raises:
            PermissionError: If Azure RBAC/Access policy denies updating secret properties.
            RuntimeError: On general Azure Key Vault API errors.
        """
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
        """Delete a secret in Azure Key Vault.

        Args:
            secret_name: Identifier or URI of secret to delete.

        Raises:
            PermissionError: If caller lacks Key Vault delete permission.
            RuntimeError: If deletion fails.
        """
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
