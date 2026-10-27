"""Main application window and GTK4 / Libadwaita presentation controller."""

from __future__ import annotations

from typing import Any, Dict, Optional, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

from src import registry, state
from src.i18n import _
from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    BaseSecretProvider,
    GCPSecretClient,
)
from src.ui.a11y import label_icon_buttons
from src.ui.dialogs.factory import DialogFactory
from src.ui.windows.actions import WindowActionsMixin
from src.ui.windows.builder import WindowBuilderMixin
from src.ui.windows.data import WindowDataMixin
from src.ui.windows.detail import WindowDetailMixin
from src.ui.windows.idle import WindowIdleLockMixin
from src.ui.windows.nav import WindowNavMixin
from src.ui.windows.shortcuts import WindowShortcutsMixin
from src.ui.windows.state import WindowState
from src.ui.windows.transfer import WindowTransferMixin


class MainWindow(
    Adw.ApplicationWindow,
    WindowNavMixin,
    WindowDetailMixin,
    WindowBuilderMixin,
    WindowDataMixin,
    WindowActionsMixin,
    WindowIdleLockMixin,
    WindowShortcutsMixin,
    WindowTransferMixin,
):
    """Primary application window for Gossip multi-cloud secret manager.

    Implements the Strategy Pattern using BaseSecretProvider instances, delegating
    provider-specific actions, labels, icons, and dialogs polymorphically.
    """

    def __init__(
        self,
        *args,
        provider: str = "gcp",
        providers: Optional[Dict[str, BaseSecretProvider]] = None,
        width: int = 1280,
        height: int = 820,
        maximized: bool = False,
        **kwargs: Any,
    ):
        """Initialize the primary application window.

        Args:
            provider: Initial provider key (see ``registry.PROVIDER_IDS``).
            providers: Ready-made clients by provider id; the missing ones are created with
                their defaults.
            width: Initial window width in pixels.
            height: Initial window height in pixels.
            maximized: Whether window starts maximized.
            **kwargs: ``<id>_client`` keywords (``gcp_client=...``) are a shorthand for
                ``providers``; everything else goes to the GTK window.
        """
        ready = dict(providers or {})
        for spec in registry.PROVIDERS:
            client = kwargs.pop(f"{spec.id}_client", None)
            if client is not None:
                ready[spec.id] = client
        super().__init__(*args, **kwargs)

        providers = registry.create_clients({}, ready)
        initial_provider_id = provider if provider in providers else "gcp"
        self.dialogs = DialogFactory()
        self.state = WindowState(
            providers=providers, active_provider=providers[initial_provider_id]
        )

        self.set_title(_("Gossip"))
        self.set_default_size(width, height)
        self.set_size_request(850, 580)
        if maximized:
            self.maximize()

        self._build_ui()
        self._setup_idle_lock()
        self._setup_shortcuts()
        label_icon_buttons(self)
        self.connect("close-request", self._save_window_state)
        GLib.idle_add(self._load_secrets_async)

    def _save_window_state(self, *_args: object) -> bool:
        """Remember the window size (or that it was maximized) for the next launch."""
        changes: Dict[str, object] = {"maximized": self.is_maximized()}
        if not self.is_maximized():
            changes.update(width=self.get_width(), height=self.get_height())
        state.update_ui(**changes)
        return False  # let the window close

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
        return cast(GCPSecretClient, self.providers["gcp"])

    @property
    def aws_client(self) -> AWSSecretClient:
        """AWS Secrets Manager provider client instance."""
        return cast(AWSSecretClient, self.providers["aws"])

    @property
    def azure_client(self) -> AzureSecretClient:
        """Azure Key Vault provider client instance."""
        return cast(AzureSecretClient, self.providers["azure"])

    @property
    def ansible_client(self) -> AnsibleVaultClient:
        """Ansible Vault provider client instance."""
        return cast(AnsibleVaultClient, self.providers["ansible"])
