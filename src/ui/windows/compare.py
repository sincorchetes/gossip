"""Comparing the selected secret with its versions or with another secret."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from src import state
from src.models import SecretItem
from src.ui.dialogs import CompareTarget
from src.ui.windows.base import WindowBase

if TYPE_CHECKING:
    from src.providers import BaseSecretProvider


def _latest_value(provider: BaseSecretProvider, secret: SecretItem) -> str:
    """Read the current value of a secret the way the exporter does."""
    versions = provider.list_versions(secret.name)
    return provider.access_secret_payload(versions[0].name)[0] if versions else ""


def _make_target(label: str, provider: BaseSecretProvider) -> CompareTarget:
    """Describe a provider (in whatever context it is configured) as a comparison source."""
    return CompareTarget(
        label=label,
        list_secrets=provider.list_secrets,
        fetch_value=lambda secret: _latest_value(provider, secret),
    )


class WindowCompareMixin(WindowBase):
    """Opens the diff windows."""

    def _on_compare_versions(self, _btn: Gtk.Button) -> None:
        """Open the diff window to compare the payloads of two versions."""
        if len(self.current_versions) < 2:
            return
        client = self.active_provider
        self._compare_dialog = self.dialogs.compare_versions(
            self,
            self.current_versions,
            lambda version_name: client.access_secret_payload(version_name)[0],
        )

    def _compare_targets(self) -> List[CompareTarget]:
        """Places to compare against: every provider in its current and recent contexts."""
        recents = state.load()["recents"]
        targets: List[CompareTarget] = []
        for provider_id, provider in self.providers.items():
            targets.append(
                _make_target(f"{provider.display_name}: {provider.context_subtitle}", provider)
            )
            if provider_id == "ansible":
                continue  # a second vault file would need its own password
            current = provider.saved_context()
            for context in recents.get(provider_id, []):
                if context == current:
                    continue
                other = type(provider)()
                other.restore_context(context)
                described = ", ".join(f"{k}={v}" for k, v in context.items())
                targets.append(_make_target(f"{provider.display_name}: {described}", other))
        return targets

    def _on_compare_with_other(self, _btn: Gtk.Button) -> None:
        """Open the dialog that diffs this secret with one from another context or provider."""
        secret = self.selected_secret
        if secret is None:
            return
        provider = self.active_provider
        label = f"{provider.display_name} / {secret.secret_id}"
        self._compare_dialog = self.dialogs.compare_secrets(
            self, label, lambda: _latest_value(provider, secret), self._compare_targets()
        )
