"""Secret lifecycle and clipboard actions mixin for MainWindow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gdk, GLib, Gtk

from src.clipboard import secret_content
from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.readonly import blocks_writes
from src.ui.windows.base import WindowBase

if TYPE_CHECKING:
    pass

# Seconds a copied secret stays on the clipboard before Gossip wipes it
CLIPBOARD_CLEAR_SECONDS = 30


class WindowActionsMixin(WindowBase):
    """Handles secret lifecycle mutation actions (create, update, delete, destroy) and clipboard."""

    if TYPE_CHECKING:

        @property
        def current_provider(self) -> str: ...

    def _show_toast(self, text: str) -> None: ...  # Defined in WindowNavMixin
    def _load_secrets_async(self) -> None: ...  # Defined in WindowDataMixin
    def _load_versions_async(self, secret_name: str) -> None: ...  # Defined in WindowDataMixin
    def _audit(
        self, action: str, secret: Optional[str] = None, **extra: object
    ) -> None: ...  # WindowNavMixin

    @blocks_writes
    def _on_create_secret_clicked(self) -> None:
        """Opens dialog to create a new secret via the active provider."""

        def on_confirm(secret_id: str, payload: str, labels: dict, desc: Optional[str] = None):
            """Process confirmed secret creation parameters from dialog."""
            self._show_toast(_("Creating secret '%s'...") % secret_id)

            provider = self.active_provider

            self._run_in_background(
                lambda: provider.create_secret(
                    secret_id=secret_id, payload_data=payload, labels=labels, description=desc
                ),
                lambda _item: self._on_secret_created_success(secret_id),
            )

        self.dialogs.create_secret(self, on_confirm, provider=self.current_provider)

    def _on_secret_created_success(self, secret_id: str) -> None:
        """Callback executed on GTK main thread after secret creation succeeds."""
        self._audit("create", secret_id)
        self._show_toast(_("Secret '%s' created successfully") % secret_id)
        self._load_secrets_async()

    @blocks_writes
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

            self._run_in_background(
                lambda: client.add_secret_version(secret_name, payload),
                lambda _item: self._on_version_added_success(),
            )

        self.dialogs.add_version(self, secret_id, on_confirm, current_value=current_value)

    def _on_version_added_success(self) -> None:
        """Callback executed on GTK main thread after new version is added."""
        if self.selected_secret:
            self._audit("add_version", self.selected_secret.secret_id)
        self._show_toast(_("New version added successfully"))
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    @blocks_writes
    def _on_toggle_version_state(self, version: SecretVersionItem, enable: bool) -> None:
        """Enables or disables a version via the active provider."""
        if enable:
            self._show_toast(_("Enabling version %s...") % version.version_id)
        else:
            self._show_toast(_("Disabling version %s...") % version.version_id)

        provider = self.active_provider

        self._run_in_background(
            lambda: provider.toggle_version_state(version.name, enable),
            lambda _result: self._on_version_state_changed_success(version.version_id, enable),
        )

    def _on_version_state_changed_success(self, version_id: str, enabled: bool) -> None:
        """Callback executed on GTK main thread after version state change succeeds."""
        if self.selected_secret:
            self._audit(
                "enable_version" if enabled else "disable_version",
                self.selected_secret.secret_id,
                version=version_id,
            )
        msg = (_("Version %s enabled") if enabled else _("Version %s disabled")) % version_id
        self._show_toast(msg)
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    @blocks_writes
    def _on_edit_metadata_clicked(self) -> None:
        """Load the current labels, let the user edit them and save the result."""
        secret = self.selected_secret
        provider = self.active_provider
        if not secret or not provider.supports_metadata_edit:
            return

        self._run_in_background(
            lambda: provider.load_metadata(secret),
            lambda metadata: self._show_metadata_dialog(secret, *metadata),
        )

    def _show_metadata_dialog(
        self, secret: SecretItem, labels: dict, description: Optional[str]
    ) -> None:
        """Open the editing dialog once the current metadata is known (GTK main thread)."""
        provider = self.active_provider

        def on_confirm(new_labels: dict, new_description: Optional[str]) -> None:
            self._show_toast(_("Saving changes to '%s'...") % secret.secret_id)

            self._run_in_background(
                lambda: provider.update_metadata(secret.name, new_labels, new_description),
                lambda _result: self._on_metadata_saved(secret),
            )

        self.dialogs.edit_metadata(
            self,
            secret.secret_id,
            labels,
            description,
            provider.supports_description_edit,
            on_confirm,
        )

    def _on_metadata_saved(self, secret: SecretItem) -> None:
        """Callback on the GTK main thread after labels were saved."""
        self._audit("edit_metadata", secret.secret_id)
        self._show_toast(_("Changes to '%s' saved") % secret.secret_id)
        self._load_secrets_async()

    @blocks_writes
    def _on_restore_version_clicked(self, version: SecretVersionItem) -> None:
        """Ask, then save the value of an older version as the new current version."""
        secret = self.selected_secret
        if not secret:
            return

        def on_confirm() -> None:
            """Copy the old value forward as a new version in the background."""
            self._show_toast(_("Restoring version %s...") % version.version_id)
            provider = self.active_provider

            def restore() -> None:
                value, _binary = provider.access_secret_payload(version.name)
                provider.add_secret_version(secret.name, value)

            self._run_in_background(
                restore, lambda _r: self._on_version_restored_success(secret, version.version_id)
            )

        self.dialogs.confirm_restore(self, version.version_id, on_confirm)

    def _on_version_restored_success(self, secret: SecretItem, version_id: str) -> None:
        """Callback on the GTK main thread after a version was restored."""
        self._audit("restore_version", secret.secret_id, version=version_id)
        self._show_toast(_("Version %s restored as the current version") % version_id)
        if self.selected_secret and self.selected_secret.name == secret.name:
            self._load_versions_async(secret.name)

    @blocks_writes
    def _on_destroy_version_clicked(self, version: SecretVersionItem) -> None:
        """Opens confirmation dialog to destroy a version via the active provider."""

        def on_confirm():
            """Process confirmed destruction of secret version."""
            self._show_toast(_("Destroying version %s...") % version.version_id)

            provider = self.active_provider

            self._run_in_background(
                lambda: provider.destroy_version(version.name),
                lambda _result: self._on_version_destroyed_success(version.version_id),
            )

        self.dialogs.confirm_destroy(self, version.version_id, on_confirm)

    def _on_version_destroyed_success(self, version_id: str) -> None:
        """Callback executed on GTK main thread after version is destroyed."""
        if self.selected_secret:
            self._audit("destroy_version", self.selected_secret.secret_id, version=version_id)
        self._show_toast(_("Version %s permanently destroyed") % version_id)
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    @blocks_writes
    def _on_delete_secret_clicked(self) -> None:
        """Opens confirmation dialog to permanently delete the secret."""
        if not self.selected_secret:
            return

        secret_id = self.selected_secret.secret_id
        secret_name = self.selected_secret.name
        client = self.active_provider

        def on_confirm(immediate: bool = False):
            """Process confirmed secret deletion (AWS may keep it recoverable for 7 days)."""
            self._show_toast(_("Deleting secret '%s'...") % secret_id)
            recoverable = client.provider_id == "aws" and not immediate

            def delete() -> None:
                if immediate:
                    client.delete_secret(secret_name, force=True)  # type: ignore[call-arg]  # AWS only
                else:
                    client.delete_secret(secret_name)

            self._run_in_background(
                delete, lambda _r: self._on_secret_deleted_success(secret_id, recoverable)
            )

        self.dialogs.confirm_delete(
            self,
            secret_id,
            on_confirm,
            provider=self.current_provider,
        )

    def _on_secret_deleted_success(self, secret_id: str, recoverable: bool = False) -> None:
        """Callback executed on GTK main thread after secret deletion succeeds."""
        self._audit("delete", secret_id, recoverable=recoverable)
        if recoverable:
            self._show_toast(
                _("Secret '%s' scheduled for deletion (recoverable for 7 days)") % secret_id
            )
        else:
            self._show_toast(_("Secret '%s' permanently deleted") % secret_id)
        self.selected_secret = None
        self.detail_stack.set_visible_child_name("placeholder")
        self._load_secrets_async()

    def _cancel_clipboard_clear(self) -> None:
        """Cancel any pending automatic clipboard wipe."""
        source_id = getattr(self, "_clipboard_clear_id", None)
        if source_id:
            GLib.source_remove(source_id)
        self._clipboard_clear_id = None

    def _clear_clipboard(self, clipboard: Gdk.Clipboard) -> bool:
        """Wipe the clipboard if Gossip still owns its content.

        Args:
            clipboard: The clipboard that received the secret.

        Returns:
            bool: Always GLib.SOURCE_REMOVE so the timer fires once.
        """
        self._clipboard_clear_id = None
        if clipboard.is_local():
            clipboard.set_content(None)
        return GLib.SOURCE_REMOVE

    def _on_copy_payload(self, _btn: Gtk.Button) -> None:
        """Copy the secret value, fetching it first when it is not loaded."""
        if self.current_payload is None:
            self._request_payload("copy")
        elif self.current_payload:
            self._copy_payload_to_clipboard(self.current_payload)

    def _on_copy_key(self, key: str, value: str) -> None:
        """Copy a single key of a multi-key secret."""
        self._copy_payload_to_clipboard(value, audit_field=key)

    def _copy_payload_to_clipboard(self, text: str, audit_field: Optional[str] = None) -> None:
        """Put a secret value on the clipboard and schedule its automatic removal."""
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set_content(secret_content(text))
        if self.selected_secret:
            if audit_field is None:
                self._audit("copy", self.selected_secret.secret_id)
            else:
                self._audit("copy_key", self.selected_secret.secret_id, field=audit_field)
        self._cancel_clipboard_clear()
        self._clipboard_clear_id = GLib.timeout_add_seconds(
            CLIPBOARD_CLEAR_SECONDS, self._clear_clipboard, clipboard
        )
        self._show_toast(_("Secret copied to clipboard"))

    def _on_copy_resource_name(self, _btn: Gtk.Button) -> None:
        """Copy full resource name/URI to system clipboard."""
        if not self.selected_secret:
            return
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.selected_secret.name)
        self._cancel_clipboard_clear()
        self._show_toast(_("Resource name copied"))
