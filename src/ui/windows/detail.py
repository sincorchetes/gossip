"""Detail panel widget construction and localization mixin for MainWindow."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import _
from src.readonly import is_read_only
from src.ui.icons import resolve_icon_name
from src.ui.windows.base import WindowBase


class WindowDetailMixin(WindowBase):
    """Constructs widgets and manages texts for the secret detail view."""

    def _build_detail_widgets(self) -> None:
        """Constructs widgets for the detail view."""
        # Top title & action buttons box
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        icon = Gtk.Image.new_from_icon_name("dialog-password-symbolic")
        icon.set_pixel_size(32)
        icon.add_css_class("accent")
        title_box.append(icon)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.detail_title = Gtk.Label(label="", xalign=0)
        self.detail_title.add_css_class("title-1")
        self.detail_title.set_selectable(True)
        text_box.append(self.detail_title)

        self.detail_resource_name = Gtk.Label(label="", xalign=0)
        self.detail_resource_name.add_css_class("caption")
        self.detail_resource_name.add_css_class("dim-label")
        self.detail_resource_name.set_selectable(True)
        text_box.append(self.detail_resource_name)
        title_box.append(text_box)

        title_box.set_hexpand(True)

        # Action button: Copy Resource Name / ARN / URI
        self.copy_name_btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text=_("Copy resource name"),
        )
        self.copy_name_btn.connect("clicked", self._on_copy_resource_name)
        title_box.append(self.copy_name_btn)

        # Action button: Add New Version
        self.add_version_btn = Gtk.Button(
            icon_name="document-new-symbolic",
            label=_("New Version"),
            tooltip_text=_("Add a new version to the secret (update value)"),
        )
        self.add_version_btn.add_css_class("suggested-action")
        self.add_version_btn.connect("clicked", lambda _: self._on_add_version_clicked())
        self.add_version_btn.set_visible(not is_read_only())
        title_box.append(self.add_version_btn)

        # Action button: Edit labels / description
        self.edit_meta_btn = Gtk.Button(
            icon_name=resolve_icon_name(
                ["document-edit-symbolic", "edit-symbolic"], fallback="document-edit-symbolic"
            ),
            tooltip_text=_("Edit labels and description"),
        )
        self.edit_meta_btn.connect("clicked", lambda _: self._on_edit_metadata_clicked())
        self.edit_meta_btn.set_visible(False)
        title_box.append(self.edit_meta_btn)

        # Action button: Delete Secret
        self.delete_secret_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text=_("Permanently delete this secret"),
        )
        self.delete_secret_btn.add_css_class("destructive-action")
        self.delete_secret_btn.connect("clicked", lambda _: self._on_delete_secret_clicked())
        self.delete_secret_btn.set_visible(not is_read_only())
        title_box.append(self.delete_secret_btn)

        self.detail_container.append(title_box)

        # Preferences Group 1: General Info
        self.info_group = Adw.PreferencesGroup(title=_("General Information"))

        self.row_description = Adw.ActionRow(title=_("Description"))
        self.row_description.set_visible(False)
        self.info_group.add(self.row_description)

        self.row_created = Adw.ActionRow(title=_("Creation date"))
        self.info_group.add(self.row_created)

        self.row_replication = Adw.ActionRow(title=_("Replication"))
        self.info_group.add(self.row_replication)

        self.row_labels = Adw.ActionRow(title=_("Labels"))
        self.info_group.add(self.row_labels)

        self.detail_container.append(self.info_group)

        # Preferences Group 2: Secret Value & Payload
        self.payload_group = Adw.PreferencesGroup(title=_("Secret Value"))

        # Version selector row
        self.row_version = Adw.ActionRow(title=_("Consulted version"))
        self.version_dropdown = Gtk.DropDown()
        self.version_dropdown.connect("notify::selected", self._on_version_changed)
        self.row_version.add_suffix(self.version_dropdown)
        self.payload_group.add(self.row_version)

        # Value display Card
        value_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        value_card.add_css_class("card")
        value_card.set_margin_top(8)
        value_card.set_margin_bottom(8)
        value_card.set_margin_start(4)
        value_card.set_margin_end(4)

        # Toolbar above value box
        val_toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        val_toolbar.set_margin_top(8)
        val_toolbar.set_margin_start(12)
        val_toolbar.set_margin_end(12)

        self.val_title = Gtk.Label(label=_("Payload:"), xalign=0)
        self.val_title.add_css_class("heading")
        self.val_title.set_hexpand(True)
        val_toolbar.append(self.val_title)

        self.payload_spinner = Gtk.Spinner()
        val_toolbar.append(self.payload_spinner)

        self.compare_btn = Gtk.Button(
            icon_name=resolve_icon_name(
                ["edit-find-replace-symbolic", "view-dual-symbolic", "edit-find-symbolic"],
                fallback="edit-find-symbolic",
            ),
            tooltip_text=_("Compare two versions"),
        )
        self.compare_btn.set_sensitive(False)
        self.compare_btn.connect("clicked", self._on_compare_versions)
        val_toolbar.append(self.compare_btn)

        self.table_btn = Gtk.ToggleButton(
            icon_name=resolve_icon_name(
                ["view-list-symbolic", "view-grid-symbolic"], fallback="view-list-symbolic"
            ),
            tooltip_text=_("Show the keys of this value as a table"),
        )
        self.table_btn.set_sensitive(False)
        self.table_btn.connect("toggled", self._on_table_toggled)
        val_toolbar.append(self.table_btn)

        self.compare_other_btn = Gtk.Button(
            icon_name=resolve_icon_name(
                ["view-dual-symbolic", "edit-find-replace-symbolic"],
                fallback="edit-find-replace-symbolic",
            ),
            tooltip_text=_("Compare with another secret (another environment or provider)"),
        )
        self.compare_other_btn.connect("clicked", self._on_compare_with_other)
        val_toolbar.append(self.compare_other_btn)

        self.reveal_btn = Gtk.Button(
            icon_name="view-reveal-symbolic",
            tooltip_text=_("Show / Hide secret"),
        )
        self.reveal_btn.connect("clicked", self._on_toggle_reveal)
        val_toolbar.append(self.reveal_btn)

        self.copy_val_btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            label=_("Copy"),
            tooltip_text=_("Copy secret to clipboard"),
        )
        self.copy_val_btn.add_css_class("suggested-action")
        self.copy_val_btn.connect("clicked", self._on_copy_payload)
        val_toolbar.append(self.copy_val_btn)

        value_card.append(val_toolbar)

        # Text View for Secret Value
        scrolled_text = Gtk.ScrolledWindow()
        scrolled_text.set_min_content_height(140)
        scrolled_text.set_max_content_height(260)
        scrolled_text.set_margin_start(12)
        scrolled_text.set_margin_end(12)
        scrolled_text.set_margin_bottom(12)

        self.text_view = Gtk.TextView()
        self.text_view.set_editable(False)
        self.text_view.set_monospace(True)
        self.text_view.set_wrap_mode(Gtk.WrapMode.CHAR)
        self.text_buffer = self.text_view.get_buffer()
        scrolled_text.set_child(self.text_view)

        # The same value as one row per key, each with its own copy button
        self.table_list = Gtk.ListBox()
        self.table_list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.table_list.add_css_class("boxed-list")
        scrolled_table = Gtk.ScrolledWindow()
        scrolled_table.set_min_content_height(140)
        scrolled_table.set_max_content_height(260)
        scrolled_table.set_margin_start(12)
        scrolled_table.set_margin_end(12)
        scrolled_table.set_margin_bottom(12)
        scrolled_table.set_child(self.table_list)

        self.value_stack = Gtk.Stack()
        self.value_stack.add_named(scrolled_text, "text")
        self.value_stack.add_named(scrolled_table, "table")
        value_card.append(self.value_stack)

        self.payload_group.add(value_card)
        self.detail_container.append(self.payload_group)

        # Preferences Group 3: Versions History
        self.versions_group = Adw.PreferencesGroup(title=_("Version History"))
        self.versions_list_box = Gtk.ListBox()
        self.versions_list_box.add_css_class("boxed-list")
        self.versions_group.add(self.versions_list_box)
        self.detail_container.append(self.versions_group)

    def _update_detail_texts(self) -> None:
        """Dynamically reload localized texts for detail panel widgets."""
        self.placeholder_page.set_title(_("No secret selected"))
        self.placeholder_page.set_description(
            _(
                "Select a secret from the sidebar to inspect its configuration, versions, and payload."
            )
        )
        self.copy_name_btn.set_tooltip_text(_("Copy resource name"))
        self.add_version_btn.set_label(_("New Version"))
        self.add_version_btn.set_tooltip_text(_("Add a new version to the secret (update value)"))
        self.delete_secret_btn.set_tooltip_text(_("Permanently delete this secret"))

        self.info_group.set_title(_("General Information"))
        self.row_description.set_title(_("Description"))
        self.row_created.set_title(_("Creation date"))
        self.row_replication.set_title(_("Replication"))
        self.row_labels.set_title(_("Labels"))

        self.payload_group.set_title(_("Secret Value"))
        self.row_version.set_title(_("Consulted version"))
        self.val_title.set_label(_("Payload:"))
        self.reveal_btn.set_tooltip_text(_("Show / Hide secret"))
        self.compare_btn.set_tooltip_text(_("Compare two versions"))
        self.copy_val_btn.set_label(_("Copy"))
        self.copy_val_btn.set_tooltip_text(_("Copy secret to clipboard"))
        self.versions_group.set_title(_("Version History"))
