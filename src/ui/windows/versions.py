"""Secret version history and payload inspection mixin for MainWindow."""

from __future__ import annotations

import os
from typing import List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.age import age_days
from src.i18n import _
from src.models import SecretVersionItem
from src.readonly import is_read_only
from src.ui.a11y import label_icon_buttons
from src.ui.icons import resolve_icon_name
from src.ui.windows.base import WindowBase


class WindowVersionsMixin(WindowBase):
    """Shows the metadata and the version history of the selected secret."""

    def _update_edit_button(self) -> None:
        """Show the edit button only where the provider can edit and writes are allowed."""
        self.edit_meta_btn.set_visible(
            self.active_provider.supports_metadata_edit and not is_read_only()
        )

    def _update_detail_labels(self) -> None:
        """Refresh the metadata labels in the detail view based on active secret and provider."""
        if not self.selected_secret:
            return
        secret = self.selected_secret
        self._update_edit_button()

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
        elif secret.provider == "vault":
            self.row_description.set_visible(False)
            self.row_replication.set_title(_("Mount"))
            self.row_replication.set_subtitle(", ".join(secret.locations))
            self.row_labels.set_visible(False)
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
        days = age_days(secret)
        if days is not None and secret.last_changed_date:
            create_str += " · " + _("changed %d days ago") % days
        self.row_created.set_subtitle(create_str)

        if self.current_versions:
            self._render_versions_list(self.current_versions)

    def _load_versions_async(self, secret_name: str) -> None:
        """Start asynchronous background loading of all versions for a secret."""
        self.payload_spinner.start()
        provider_id = self.active_provider.provider_id
        client = self.active_provider

        self._run_in_background(
            lambda: client.list_versions(secret_name),
            lambda versions: self._on_versions_loaded(versions, None, secret_name, provider_id),
            lambda exc: self._on_versions_loaded([], str(exc), secret_name, provider_id),
        )

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
        if not self.state.is_selected(secret_name):
            return

        self.payload_spinner.stop()

        if error:
            self._show_toast(_("Error: {detail}").format(detail=error))
            return

        self.current_versions = versions
        self._render_versions_list(versions)

        # The value itself is only fetched when the user reveals or copies it
        self._reset_payload()
        self.copy_val_btn.set_sensitive(bool(versions))
        if not versions:
            self.text_buffer.set_text(_("[No active versions]"))

    def _create_version_action_buttons(self, action_box: Gtk.Box, v: SecretVersionItem) -> None:
        """Add toggle and destroy action buttons for a secret version."""
        if is_read_only():
            return
        if v.state == "ENABLED":
            pause_btn = Gtk.Button(
                icon_name="media-playback-pause-symbolic",
                tooltip_text=_("Disable version %s") % v.version_id,
            )
            pause_btn.add_css_class("flat")
            pause_btn.connect(
                "clicked",
                lambda _, ver=v: self._on_toggle_version_state(ver, enable=False),
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
                lambda _, ver=v: self._on_toggle_version_state(ver, enable=True),
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
                lambda _, ver=v: self._on_destroy_version_clicked(ver),
            )
            action_box.append(destroy_btn)

    def _create_restore_button(self, action_box: Gtk.Box, v: SecretVersionItem) -> None:
        """Offer to save an older, readable version again as the current one."""
        if (
            is_read_only()
            or not self.active_provider.supports_version_restore
            or v.state in ("DESTROYED", "DISABLED")
        ):
            return
        restore_btn = Gtk.Button(
            icon_name=resolve_icon_name(
                ["edit-undo-symbolic", "document-revert-symbolic"], fallback="edit-undo-symbolic"
            ),
            tooltip_text=_("Restore version %s as the current version") % v.version_id,
        )
        restore_btn.add_css_class("flat")
        restore_btn.connect("clicked", lambda _b, ver=v: self._on_restore_version_clicked(ver))
        action_box.append(restore_btn)

    def _render_versions_list(self, versions: List[SecretVersionItem]) -> None:
        """Render rows for each secret version inside the versions list container."""
        while True:
            row = self.versions_list_box.get_row_at_index(0)
            if row is None:
                break
            self.versions_list_box.remove(row)

        provider = self.active_provider

        for index, v in enumerate(versions):
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

            if index > 0:
                self._create_restore_button(action_box, v)
            action_box.append(state_label)
            v_row.add_suffix(action_box)
            self.versions_list_box.append(v_row)
            label_icon_buttons(v_row)

        dropdown_items = [f"{_('Version %s') % v.version_id} ({v.display_state})" for v in versions]
        if not dropdown_items:
            dropdown_items = [_("Latest")]

        self.compare_btn.set_sensitive(len(versions) >= 2)

        string_list = Gtk.StringList.new(dropdown_items)
        self.version_dropdown.set_model(string_list)
        self.version_dropdown.set_selected(0)

    def _on_version_changed(self, dropdown: Gtk.DropDown, _param) -> None:
        """Handle a version selection change, reloading the value only if it was revealed."""
        was_revealed = self.is_payload_revealed
        self._reset_payload()
        if was_revealed:
            self._request_payload("reveal")
