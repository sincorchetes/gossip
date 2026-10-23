"""Secret version history and payload inspection mixin for MainWindow."""

from __future__ import annotations

import os
import threading
from typing import TYPE_CHECKING, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.models import SecretItem, SecretVersionItem

if TYPE_CHECKING:
    from src.providers import BaseSecretProvider


class WindowVersionsMixin:
    """Manages secret version history query, state changes, and payload viewing."""

    # UI widget references
    row_description: Adw.ActionRow
    row_replication: Adw.ActionRow
    row_labels: Adw.ActionRow
    row_created: Adw.ActionRow
    payload_spinner: Gtk.Spinner
    text_buffer: Gtk.TextBuffer
    reveal_btn: Gtk.Button
    copy_val_btn: Gtk.Button
    versions_list_box: Gtk.ListBox
    version_dropdown: Gtk.DropDown

    # State attributes
    active_provider: BaseSecretProvider
    selected_secret: Optional[SecretItem]
    current_versions: List[SecretVersionItem]
    current_payload: Optional[str]
    is_payload_revealed: bool

    def _update_detail_labels(self) -> None:
        """Refresh the metadata labels in the detail view based on active secret and provider."""
        if not self.selected_secret:
            return
        secret = self.selected_secret

        if secret.provider == "ansible":
            self.row_description.set_title(_("Type / Length"))
            self.row_description.set_subtitle(secret.description or "")
            self.row_description.set_visible(True)
            self.row_replication.set_title(_("Vault File"))
            vf = getattr(self.active_provider, "vault_file", "") or ""
            self.row_replication.set_subtitle(os.path.basename(vf))
            self.row_labels.set_title(_("Data Type"))
            self.row_labels.set_subtitle(secret.labels.get("type", "string"))
            self.row_labels.set_visible(True)
        else:
            if secret.description:
                desc_title = (
                    _("Content Type / Description")
                    if secret.provider == "azure"
                    else _("Description")
                )
                self.row_description.set_title(desc_title)
                self.row_description.set_subtitle(secret.description)
                self.row_description.set_visible(True)
            else:
                self.row_description.set_visible(False)

            self.row_replication.set_title(_("Replication"))
            self.row_replication.set_subtitle(secret.replication_summary)

            if secret.labels:
                tag_label_title = _("Tags") if secret.provider in ("aws", "azure") else _("Labels")
                self.row_labels.set_title(tag_label_title)
                labels_str = ", ".join(f"{k}: {v}" for k, v in secret.labels.items())
                self.row_labels.set_subtitle(labels_str)
                self.row_labels.set_visible(True)
            else:
                self.row_labels.set_subtitle(_("No labels"))

        create_str = (
            secret.create_time.strftime("%d/%m/%Y %H:%M:%S") if secret.create_time else _("Unknown")
        )
        self.row_created.set_subtitle(create_str)

        if self.current_versions:
            self._render_versions_list(self.current_versions)

    def _load_versions_async(self, secret_name: str) -> None:
        """Start asynchronous background loading of all versions for a secret."""
        self.payload_spinner.start()
        provider_id = self.active_provider.provider_id
        client = self.active_provider

        def worker() -> None:
            """Background worker thread fetching versions from the active provider."""
            try:
                versions = client.list_versions(secret_name)
                GLib.idle_add(self._on_versions_loaded, versions, None, secret_name, provider_id)
            except Exception as exc:
                GLib.idle_add(self._on_versions_loaded, [], str(exc), secret_name, provider_id)

        threading.Thread(target=worker, daemon=True).start()

    def _on_versions_loaded(
        self,
        versions: List[SecretVersionItem],
        error: Optional[str],
        secret_name: str,
        provider_id: str,
    ) -> None:
        """Handle completion of the version history query on the GTK main thread."""
        if provider_id != self.active_provider.provider_id:
            return
        if not self.selected_secret or self.selected_secret.name != secret_name:
            return

        self.payload_spinner.stop()

        if error:
            self._show_toast(f"Error: {error}")  # type: ignore[attr-defined]
            return

        self.current_versions = versions
        self._render_versions_list(versions)

        # Load payload of the selected version
        if versions:
            self._load_payload_async(versions[0].name)
        else:
            self.text_buffer.set_text(_("[No active versions]"))

    def _create_version_action_buttons(self, action_box: Gtk.Box, v: SecretVersionItem) -> None:
        """Add toggle and destroy action buttons for a secret version."""
        if v.state == "ENABLED":
            pause_btn = Gtk.Button(
                icon_name="media-playback-pause-symbolic",
                tooltip_text=_("Disable version %s") % v.version_id,
            )
            pause_btn.add_css_class("flat")
            pause_btn.connect(
                "clicked",
                lambda _, ver=v: self._on_toggle_version_state(ver, enable=False),  # type: ignore[attr-defined]
            )
            action_box.append(pause_btn)
        elif v.state == "DISABLED":
            play_btn = Gtk.Button(
                icon_name="media-playback-start-symbolic",
                tooltip_text=_("Enable version %s") % v.version_id,
            )
            play_btn.add_css_class("flat")
            play_btn.connect(
                "clicked",
                lambda _, ver=v: self._on_toggle_version_state(ver, enable=True),  # type: ignore[attr-defined]
            )
            action_box.append(play_btn)

        if self.active_provider.supports_version_destroy:
            destroy_btn = Gtk.Button(
                icon_name="edit-delete-symbolic",
                tooltip_text=_("Permanently destroy version %s") % v.version_id,
            )
            destroy_btn.add_css_class("flat")
            destroy_btn.add_css_class("destructive-action")
            destroy_btn.connect(
                "clicked",
                lambda _, ver=v: self._on_destroy_version_clicked(ver),  # type: ignore[attr-defined]
            )
            action_box.append(destroy_btn)

    def _render_versions_list(self, versions: List[SecretVersionItem]) -> None:
        """Render rows for each secret version inside the versions list container."""
        while True:
            row = self.versions_list_box.get_row_at_index(0)
            if row is None:
                break
            self.versions_list_box.remove(row)

        provider = self.active_provider

        for v in versions:
            v_title = _("Version %s") % v.version_id
            v_row = Adw.ActionRow(title=v_title)
            dt = v.create_time.strftime("%d/%m/%Y %H:%M") if v.create_time else ""
            v_row.set_subtitle(_("Created: %s") % dt)

            # Horizontal action box
            action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

            # State pill
            state_label = Gtk.Label(label=v.display_state)
            state_label.add_css_class("pill")

            if provider.supports_version_toggling:
                if v.state == "ENABLED":
                    state_label.add_css_class("success")
                    self._create_version_action_buttons(action_box, v)
                elif v.state == "DISABLED":
                    state_label.add_css_class("warning")
                    self._create_version_action_buttons(action_box, v)
                else:
                    state_label.add_css_class("error")
            else:
                if "AWSCURRENT" in v.stages:
                    state_label.add_css_class("success")
                elif "AWSPREVIOUS" in v.stages:
                    state_label.add_css_class("warning")
                else:
                    state_label.add_css_class("caption")

            action_box.append(state_label)
            v_row.add_suffix(action_box)
            self.versions_list_box.append(v_row)

        dropdown_items = [f"{_('Version %s') % v.version_id} ({v.display_state})" for v in versions]
        if not dropdown_items:
            dropdown_items = ["latest"]

        string_list = Gtk.StringList.new(dropdown_items)
        self.version_dropdown.set_model(string_list)
        self.version_dropdown.set_selected(0)

    def _on_version_changed(self, dropdown: Gtk.DropDown, _param) -> None:
        """Handle selection change in the version dropdown."""
        idx = dropdown.get_selected()
        if 0 <= idx < len(self.current_versions):
            selected_v = self.current_versions[idx]
            self._load_payload_async(selected_v.name)

    def _load_payload_async(self, version_name: str) -> None:
        """Start asynchronous background loading of secret payload value."""
        self.payload_spinner.start()
        self.copy_val_btn.set_sensitive(False)
        self.text_buffer.set_text(_("Fetching secret..."))
        provider_id = self.active_provider.provider_id
        client = self.active_provider

        def worker() -> None:
            """Background worker thread retrieving secret payload data."""
            try:
                payload, is_binary = client.access_secret_payload(version_name)
                GLib.idle_add(self._on_payload_loaded, payload, is_binary, None, provider_id)
            except Exception as exc:
                GLib.idle_add(self._on_payload_loaded, None, False, str(exc), provider_id)

        threading.Thread(target=worker, daemon=True).start()

    def _on_payload_loaded(
        self,
        payload: Optional[str],
        is_binary: bool,
        error: Optional[str],
        provider_id: str,
    ) -> None:
        """Handle completion of payload query on the GTK main thread."""
        if provider_id != self.active_provider.provider_id:
            return

        self.payload_spinner.stop()

        if error:
            self.current_payload = None
            self.text_buffer.set_text(f"Error: {error}")
            self.copy_val_btn.set_sensitive(False)
            return

        self.current_payload = payload
        self.copy_val_btn.set_sensitive(True)
        self._render_payload_text()

    def _render_payload_text(self) -> None:
        """Update the payload TextView buffer with either masked or clear text."""
        if not self.current_payload:
            self.text_buffer.set_text("")
            return

        if self.is_payload_revealed:
            self.text_buffer.set_text(self.current_payload)
            self.reveal_btn.set_icon_name("view-conceal-symbolic")
        else:
            masked = "•" * min(len(self.current_payload), 48)
            self.text_buffer.set_text(masked)
            self.reveal_btn.set_icon_name("view-reveal-symbolic")

    def _on_toggle_reveal(self, _btn: Gtk.Button) -> None:
        """Toggle between masked dots and revealed plaintext for secret payload."""
        self.is_payload_revealed = not self.is_payload_revealed
        self._render_payload_text()
