"""Main application window and GTK4 / Libadwaita presentation controller."""

from __future__ import annotations

from typing import Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    BaseSecretProvider,
    GCPSecretClient,
)
from src.ui.dialogs import (
    show_about_dialog,
    show_add_version_dialog,
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_create_secret_dialog,
)
from src.ui.icons import resolve_icon_name
from src.ui.window_actions import WindowActionsMixin
from src.ui.window_builder import WindowBuilderMixin
from src.ui.window_data import WindowDataMixin
from src.ui.window_detail import WindowDetailMixin
from src.ui.window_nav import WindowNavMixin

__all__ = [
    "MainWindow",
    "resolve_icon_name",
    "show_about_dialog",
    "show_add_version_dialog",
    "show_confirm_delete_secret_dialog",
    "show_confirm_destroy_version_dialog",
    "show_create_secret_dialog",
]


class MainWindow(
    Adw.ApplicationWindow,
    WindowNavMixin,
    WindowDetailMixin,
    WindowBuilderMixin,
    WindowDataMixin,
    WindowActionsMixin,
):
    """Primary application window for Gossip multi-cloud secret manager.

    Implements the Strategy Pattern using BaseSecretProvider instances, delegating
    provider-specific actions, labels, icons, and dialogs polymorphically.
    """

    def __init__(
        self,
        *args,
        provider: str = "gcp",
        gcp_client: Optional[GCPSecretClient] = None,
        aws_client: Optional[AWSSecretClient] = None,
        azure_client: Optional[AzureSecretClient] = None,
        ansible_client: Optional[AnsibleVaultClient] = None,
        width: int = 1280,
        height: int = 820,
        maximized: bool = False,
        **kwargs,
    ):
        """Initialize the primary application window.

        Args:
            provider: Initial provider key ('gcp', 'aws', 'azure', 'ansible').
            gcp_client: Optional preconfigured GCPSecretClient instance.
            aws_client: Optional preconfigured AWSSecretClient instance.
            azure_client: Optional preconfigured AzureSecretClient instance.
            ansible_client: Optional preconfigured AnsibleVaultClient instance.
            width: Initial window width in pixels.
            height: Initial window height in pixels.
            maximized: Whether window starts maximized.
        """
        super().__init__(*args, **kwargs)

        self.providers: Dict[str, BaseSecretProvider] = {
            "gcp": gcp_client or GCPSecretClient(),
            "aws": aws_client or AWSSecretClient(),
            "azure": azure_client or AzureSecretClient(),
            "ansible": ansible_client or AnsibleVaultClient(),
        }

        initial_provider_id = provider if provider in self.providers else "gcp"
        self.active_provider: BaseSecretProvider = self.providers[initial_provider_id]

        self.secrets: List[SecretItem] = []
        self.selected_secret: Optional[SecretItem] = None
        self.current_versions: List[SecretVersionItem] = []
        self.current_payload: Optional[str] = None
        self.is_payload_revealed: bool = False

        self.set_title(_("Gossip"))
        self.set_default_size(width, height)
        self.set_size_request(850, 580)
        if maximized:
            self.maximize()

        self._build_ui()
        GLib.idle_add(self._load_secrets_async)

    # -------------------------------------------------------------
    # Provider Accessors (Strategy Pattern)
    # -------------------------------------------------------------
    @property
    def client(self) -> BaseSecretProvider:
        """Returns the currently active secret provider strategy."""
        return self.active_provider

    @property
    def current_provider(self) -> str:
        """Identifier of the active provider ('gcp', 'aws', 'azure', 'ansible')."""
        return self.active_provider.provider_id

    @property
    def gcp_client(self) -> GCPSecretClient:
        """GCP Secret Manager provider client instance."""
        return self.providers["gcp"]  # type: ignore[return-value]

    @property
    def aws_client(self) -> AWSSecretClient:
        """AWS Secrets Manager provider client instance."""
        return self.providers["aws"]  # type: ignore[return-value]

    @property
    def azure_client(self) -> AzureSecretClient:
        """Azure Key Vault provider client instance."""
        return self.providers["azure"]  # type: ignore[return-value]

    @property
    def ansible_client(self) -> AnsibleVaultClient:
        """Ansible Vault provider client instance."""
        return self.providers["ansible"]  # type: ignore[return-value]
