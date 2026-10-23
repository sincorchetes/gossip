"""Microsoft Azure Key Vault secret provider implementation."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.i18n import _
from src.models import AzureVaultItem, SecretVersionItem
from src.providers.azure_discovery import (
    detect_vault_name,
    list_available_vaults,
)
from src.providers.azure_ops import AzureOperationsMixin
from src.providers.base import BaseSecretProvider

__all__ = ["AzureSecretClient", "DefaultAzureCredential", "SecretClient"]


class AzureSecretClient(AzureOperationsMixin, BaseSecretProvider):
    """Provider implementation for Azure Key Vault."""

    def __init__(self, vault_name: Optional[str] = None):
        """Initialize the Azure Key Vault client.

        Args:
            vault_name: Optional Key Vault name or URI. If omitted, attempts autodetection.
        """
        self._vault_name = vault_name
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
            self.vault_name = vault_name
            on_success()

        show_change_azure_vault_dialog(parent_window, self, on_confirm)

    def toggle_version_state(self, version: str | SecretVersionItem, enable: bool) -> None:
        """Enable or disable a specific Azure Key Vault secret version."""
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
        """Detect active Azure Key Vault name from environment variables."""
        return detect_vault_name()

    def list_available_vaults(self) -> List[AzureVaultItem]:
        """List accessible Azure Key Vaults discovered via Azure CLI."""
        return list_available_vaults(self.vault_name, self.vault_url)


__all__ = ["AzureSecretClient"]
