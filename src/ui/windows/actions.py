"""Secret lifecycle and clipboard actions mixin for MainWindow."""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, GLib, Gtk

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.ui.dialogs import (
    show_add_version_dialog,
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_create_secret_dialog,
)

if TYPE_CHECKING:
    from src.providers import BaseSecretProvider


class WindowActionsMixin:
    """Handles secret lifecycle mutation actions (create, update, delete, destroy) and clipboard."""

    active_provider: BaseSecretProvider
    current_provider: str
    selected_secret: Optional[SecretItem]
    current_payload: Optional[str]
    current_versions: list[SecretVersionItem]
    detail_stack: Gtk.Stack

    def _show_toast(self, text: str) -> None: ...  # Defined in WindowNavMixin
    def _load_secrets_async(self) -> None: ...  # Defined in WindowDataMixin
    def _load_versions_async(self, secret_name: str) -> None: ...  # Defined in WindowDataMixin

    def _on_create_secret_clicked(self) -> None:
        """Opens dialog to create a new secret via the active provider."""

        def on_confirm(secret_id: str, payload: str, labels: dict, desc: Optional[str] = None):
            """Process confirmed secret creation parameters from dialog."""
            self._show_toast(_("Creating secret '%s'...") % secret_id)

            provider = self.active_provider

            def worker() -> None:
                """Background worker thread creating secret in the active provider."""
                try:
                    provider.create_secret(
                        secret_id=secret_id,
                        payload_data=payload,
                        labels=labels,
                        description=desc,
                    )
                    GLib.idle_add(self._on_secret_created_success, secret_id)
                except Exception as exc:
                    GLib.idle_add(self._show_toast, f"Error: {exc}")

            threading.Thread(target=worker, daemon=True).start()

        win_mod = sys.modules.get("src.ui.window") or sys.modules.get("src.ui.windows")
        dlg_fn = getattr(win_mod, "show_create_secret_dialog", show_create_secret_dialog)
        dlg_fn(self, on_confirm, provider=self.current_provider)  # type: ignore[arg-type]

    def _on_secret_created_success(self, secret_id: str) -> None:
        """Callback executed on GTK main thread after secret creation succeeds."""
        self._show_toast(_("Secret '%s' created successfully") % secret_id)
        self._load_secrets_async()

    def _on_add_version_clicked(self) -> None:
        """Opens dialog to add a new version to the selected secret."""
        if not self.selected_secret:
            return

        secret_id = self.selected_secret.secret_id
        secret_name = self.selected_secret.name
        client = self.active_provider

        current_value = self.current_payload
        if current_value is None and self.current_versions:
            try:
                current_value, _is_bin = client.access_secret_payload(self.current_versions[0].name)
            except Exception:
                current_value = None

        def on_confirm(payload: str):
            """Process confirmed payload to append as a new version."""
            self._show_toast(_("Adding new version..."))

            def worker() -> None:
                """Background worker thread adding a new version."""
                try:
                    client.add_secret_version(secret_name, payload)
                    GLib.idle_add(self._on_version_added_success)
                except Exception as exc:
                    GLib.idle_add(self._show_toast, f"Error: {exc}")

            threading.Thread(target=worker, daemon=True).start()

        win_mod = sys.modules.get("src.ui.window") or sys.modules.get("src.ui.windows")
        dlg_fn = getattr(win_mod, "show_add_version_dialog", show_add_version_dialog)
        dlg_fn(self, secret_id, on_confirm, current_value=current_value)  # type: ignore[arg-type]

    def _on_version_added_success(self) -> None:
        """Callback executed on GTK main thread after new version is added."""
        self._show_toast(_("New version added successfully"))
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    def _on_toggle_version_state(self, version: SecretVersionItem, enable: bool) -> None:
        """Enables or disables a version via the active provider."""
        if enable:
            self._show_toast(_("Enabling version %s...") % version.version_id)
        else:
            self._show_toast(_("Disabling version %s...") % version.version_id)

        provider = self.active_provider

        def worker() -> None:
            """Background worker thread updating version state."""
            try:
                provider.toggle_version_state(version.name, enable)
                GLib.idle_add(self._on_version_state_changed_success, version.version_id, enable)
            except Exception as exc:
                GLib.idle_add(self._show_toast, f"Error: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_version_state_changed_success(self, version_id: str, enabled: bool) -> None:
        """Callback executed on GTK main thread after version state change succeeds."""
        msg = (_("Version %s enabled") if enabled else _("Version %s disabled")) % version_id
        self._show_toast(msg)
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    def _on_destroy_version_clicked(self, version: SecretVersionItem) -> None:
        """Opens confirmation dialog to destroy a version via the active provider."""

        def on_confirm():
            """Process confirmed destruction of secret version."""
            self._show_toast(_("Destroying version %s...") % version.version_id)

            provider = self.active_provider

            def worker() -> None:
                """Background worker thread permanently destroying version."""
                try:
                    provider.destroy_version(version.name)
                    GLib.idle_add(self._on_version_destroyed_success, version.version_id)
                except Exception as exc:
                    GLib.idle_add(self._show_toast, f"Error: {exc}")

            threading.Thread(target=worker, daemon=True).start()

        win_mod = sys.modules.get("src.ui.window") or sys.modules.get("src.ui.windows")
        dlg_fn = getattr(
            win_mod, "show_confirm_destroy_version_dialog", show_confirm_destroy_version_dialog
        )
        dlg_fn(self, version.version_id, on_confirm)  # type: ignore[arg-type]

    def _on_version_destroyed_success(self, version_id: str) -> None:
        """Callback executed on GTK main thread after version is destroyed."""
        self._show_toast(_("Version %s permanently destroyed") % version_id)
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    def _on_delete_secret_clicked(self) -> None:
        """Opens confirmation dialog to permanently delete the secret."""
        if not self.selected_secret:
            return

        secret_id = self.selected_secret.secret_id
        secret_name = self.selected_secret.name
        client = self.active_provider

        def on_confirm():
            """Process confirmed secret deletion."""
            self._show_toast(_("Deleting secret '%s'...") % secret_id)

            def worker() -> None:
                """Background worker thread deleting secret."""
                try:
                    client.delete_secret(secret_name)
                    GLib.idle_add(self._on_secret_deleted_success, secret_id)
                except Exception as exc:
                    GLib.idle_add(self._show_toast, f"Error: {exc}")

            threading.Thread(target=worker, daemon=True).start()

        win_mod = sys.modules.get("src.ui.window") or sys.modules.get("src.ui.windows")
        dlg_fn = getattr(
            win_mod, "show_confirm_delete_secret_dialog", show_confirm_delete_secret_dialog
        )
        dlg_fn(
            self,
            secret_id,
            on_confirm,
            provider=self.current_provider,  # type: ignore[arg-type]
        )

    def _on_secret_deleted_success(self, secret_id: str) -> None:
        """Callback executed on GTK main thread after secret deletion succeeds."""
        self._show_toast(_("Secret '%s' permanently deleted") % secret_id)
        self.selected_secret = None
        self.detail_stack.set_visible_child_name("placeholder")
        self._load_secrets_async()

    def _on_copy_payload(self, _btn: Gtk.Button) -> None:
        """Copy active secret plaintext payload to system clipboard."""
        if not self.current_payload:
            return
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.current_payload)
        self._show_toast(_("Secret copied to clipboard"))

    def _on_copy_resource_name(self, _btn: Gtk.Button) -> None:
        """Copy full resource name/URI to system clipboard."""
        if not self.selected_secret:
            return
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.selected_secret.name)
        self._show_toast(_("Resource name copied"))
