"""HashiCorp Vault / OpenBao provider (KV version 2)."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from src.i18n import _
from src.providers.base import BaseSecretProvider
from src.providers.vault.api import VaultHTTP
from src.providers.vault.discovery import (
    detect_address,
    detect_cafile,
    detect_namespace,
    detect_token,
    normalize_address,
    normalize_mount,
)
from src.providers.vault.ops import VaultOperationsMixin


class VaultClient(VaultOperationsMixin, BaseSecretProvider):
    """Provider for HashiCorp Vault and OpenBao servers using the KV v2 engine."""

    def __init__(
        self,
        address: Optional[str] = None,
        mount: Optional[str] = None,
        namespace: Optional[str] = None,
    ):
        """Initialize the client.

        Args:
            address: Server URL; falls back to VAULT_ADDR / BAO_ADDR.
            mount: KV v2 mount path (default "secret").
            namespace: Optional namespace; falls back to VAULT_NAMESPACE / BAO_NAMESPACE.
        """
        self._address = address
        self.mount = normalize_mount(mount)
        self._namespace = namespace
        self._typed_token: Optional[str] = None
        self._http_client: Optional[VaultHTTP] = None

    @property
    def provider_id(self) -> str:
        """Return the unique provider identifier string ('vault')."""
        return "vault"

    @property
    def display_name(self) -> str:
        """Return the human-readable provider name shown in the UI switcher."""
        return "HashiCorp Vault / OpenBao"

    @property
    def icon_name(self) -> str:
        """Return the symbolic icon name for the context switcher button."""
        return "security-high-symbolic"

    @property
    def context_subtitle(self) -> str:
        """Return the subtitle with the active server and mount."""
        if not self.address:
            return _("Vault: no server selected")
        return _("Vault: %s") % f"{self.address} ({self.mount})"

    @property
    def context_btn_tooltip(self) -> str:
        """Return the tooltip for the server switcher button."""
        return _("Change Vault server")

    @property
    def loading_message(self) -> str:
        """Return the message shown while querying the server."""
        return _("Querying Vault...")

    @property
    def empty_message(self) -> str:
        """Return the message shown when the mount has no secrets."""
        return _("No secrets found in this Vault mount.")

    @property
    def error_message(self) -> str:
        """Return the message shown when connection or query fails."""
        return _("Could not connect to Vault.")

    @property
    def supports_metadata_edit(self) -> bool:
        """Custom metadata can be edited."""
        return True

    @property
    def supports_version_toggling(self) -> bool:
        """KV v2 can soft-delete and undelete versions."""
        return True

    @property
    def supports_version_destroy(self) -> bool:
        """KV v2 can permanently destroy the data of a version."""
        return True

    @property
    def address(self) -> Optional[str]:
        """Return the active server URL."""
        return self._address or detect_address()

    @property
    def namespace(self) -> Optional[str]:
        """Return the active namespace."""
        return self._namespace or detect_namespace()

    def configure(
        self,
        address: str,
        mount: Optional[str],
        namespace: Optional[str],
        token: Optional[str],
    ) -> None:
        """Apply the settings chosen in the context dialog.

        Raises:
            ValueError: If the address is not acceptable (see normalize_address).
        """
        self._address = normalize_address(address)
        self.mount = normalize_mount(mount)
        self._namespace = (namespace or "").strip() or None
        self._typed_token = token or None
        self._http_client = None

    def saved_context(self) -> Dict[str, str]:
        """Return server, mount and namespace (never the token)."""
        context = {"address": self._address, "mount": self.mount, "namespace": self._namespace}
        return {k: v for k, v in context.items() if v}

    def restore_context(self, context: Dict[str, str]) -> None:
        """Re-select the remembered server, mount and namespace."""
        try:
            if context.get("address"):
                self._address = normalize_address(context["address"])
        except ValueError:
            return
        if context.get("mount"):
            self.mount = normalize_mount(context["mount"])
        self._namespace = context.get("namespace") or self._namespace
        self._http_client = None

    def lock(self) -> None:
        """Forget the token typed by the user (tokens from the environment are re-read)."""
        self._typed_token = None
        self._http_client = None

    def _http(self) -> VaultHTTP:
        """Build (and cache) the HTTP client, validating address and token first."""
        if self._http_client is not None:
            return self._http_client
        if not self.address:
            raise ValueError(
                _(
                    "No Vault server configured.\n"
                    "Use the server button to enter its address or set VAULT_ADDR."
                )
            )
        token = self._typed_token or detect_token()
        if not token:
            raise PermissionError(
                _(
                    "No Vault token available.\n"
                    "Enter it in the server dialog, set VAULT_TOKEN or run 'vault login'."
                )
            )
        self._http_client = VaultHTTP(
            normalize_address(self.address), token, self.namespace, detect_cafile()
        )
        return self._http_client

    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        """Open the dialog to choose server, mount, namespace and token."""
        from src.ui.dialogs import show_change_vault_dialog

        show_change_vault_dialog(parent_window, self, on_success)
