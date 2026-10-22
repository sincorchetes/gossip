"""Main application window and GTK4 / Libadwaita presentation controller."""

from __future__ import annotations

import os
import threading
from typing import Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    BaseSecretProvider,
    GCPSecretClient,
)
from src.i18n import _, get_current_language, set_language
from src.models import SecretItem, SecretVersionItem
from src.ui.dialogs import (
    show_about_dialog,
    show_add_version_dialog,
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_create_secret_dialog,
)


class MainWindow(Adw.ApplicationWindow):
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
        self._load_secrets_async()

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

    # -------------------------------------------------------------
    # Dynamic Context Properties (Polymorphic Delegation)
    # -------------------------------------------------------------
    def _get_context_subtitle(self) -> str:
        """Retrieve contextual subtitle from the active provider."""
        return self.active_provider.context_subtitle

    def _get_context_btn_tooltip(self) -> str:
        """Retrieve tooltip text for the context switcher button."""
        return self.active_provider.context_btn_tooltip

    def _get_context_btn_icon(self) -> str:
        """Retrieve icon name for the active provider."""
        return self.active_provider.icon_name

    def _get_loading_text(self) -> str:
        """Retrieve loading text for the active provider."""
        return self.active_provider.loading_message

    def _get_empty_text(self) -> str:
        """Retrieve empty state message for the active provider."""
        return self.active_provider.empty_message

    def _get_error_text(self) -> str:
        """Retrieve error state message for the active provider."""
        return self.active_provider.error_message

    # -------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------
    def _build_ui(self) -> None:
        """Construct the complete GTK4 and Libadwaita user interface layout."""
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)

        # 1. HeaderBar
        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(
            title=_("Gossip"),
            subtitle=self._get_context_subtitle(),
        )
        header.set_title_widget(self.window_title)

        # Provider switcher (GCP / AWS / Azure / Ansible)
        provider_keys = list(self.providers.keys())
        provider_display_names = [self.providers[k].display_name for k in provider_keys]
        self.provider_dropdown = Gtk.DropDown.new_from_strings(provider_display_names)
        initial_idx = provider_keys.index(self.active_provider.provider_id)
        self.provider_dropdown.set_selected(initial_idx)
        self.provider_dropdown.connect("notify::selected", self._on_provider_changed)
        header.pack_start(self.provider_dropdown)

        # Context switch button (Project for GCP, Profile/Region for AWS, Vault for Azure/Ansible)
        self.context_btn = Gtk.Button(
            icon_name=self._get_context_btn_icon(),
            tooltip_text=self._get_context_btn_tooltip(),
        )
        self.context_btn.connect("clicked", self._on_change_context_clicked)
        header.pack_start(self.context_btn)

        self.refresh_btn = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text=_("Reload secrets"),
        )
        self.refresh_btn.connect("clicked", lambda _: self._load_secrets_async())
        header.pack_start(self.refresh_btn)

        # End buttons: Language toggle (ES/EN), Theme toggle, About
        self.lang_btn = Gtk.Button(
            label=get_current_language().upper(),
            tooltip_text=_("Switch language (ES / EN)"),
        )
        self.lang_btn.add_css_class("flat")
        self.lang_btn.connect("clicked", self._toggle_language)
        header.pack_end(self.lang_btn)

        self.theme_btn = Gtk.Button(
            icon_name="weather-clear-night-symbolic",
            tooltip_text=_("Toggle light/dark theme"),
        )
        self.theme_btn.connect("clicked", self._toggle_theme)
        header.pack_end(self.theme_btn)

        self.about_btn = Gtk.Button(
            icon_name="help-about-symbolic",
            tooltip_text=_("About Gossip"),
        )
        self.about_btn.connect("clicked", lambda _: show_about_dialog(self))
        header.pack_end(self.about_btn)

        main_box.append(header)

        # Banner for warnings / auth errors
        self.banner = Adw.Banner()
        self.banner.set_revealed(False)
        main_box.append(self.banner)

        # 2. Main Paned Layout (Sidebar + Detail)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(360)
        paned.set_wide_handle(True)
        paned.set_vexpand(True)
        paned.set_hexpand(True)
        main_box.append(paned)

        # Left: Sidebar
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar_box.set_margin_top(8)
        sidebar_box.set_margin_bottom(8)
        sidebar_box.set_margin_start(8)
        sidebar_box.set_margin_end(8)
        sidebar_box.set_size_request(300, -1)

        # Search Bar + "+ Nuevo Secreto" Button
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search secrets..."))
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.set_hexpand(True)
        search_box.append(self.search_entry)

        self.add_secret_btn = Gtk.Button(
            icon_name="list-add-symbolic",
            tooltip_text=_("Create new secret"),
        )
        self.add_secret_btn.add_css_class("suggested-action")
        self.add_secret_btn.connect("clicked", lambda _: self._on_create_secret_clicked())
        search_box.append(self.add_secret_btn)
        sidebar_box.append(search_box)

        # Stack for Sidebar states: loading, list, empty, error
        self.sidebar_stack = Gtk.Stack()
        self.sidebar_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        sidebar_box.append(self.sidebar_stack)

        # Sidebar: Loading
        loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        loading_box.set_valign(Gtk.Align.CENTER)
        loading_box.set_halign(Gtk.Align.CENTER)
        self.sidebar_spinner = Gtk.Spinner()
        self.sidebar_spinner.set_size_request(36, 36)
        loading_box.append(self.sidebar_spinner)
        self.loading_label = Gtk.Label(label=self._get_loading_text())
        self.loading_label.add_css_class("dim-label")
        loading_box.append(self.loading_label)
        self.sidebar_stack.add_named(loading_box, "loading")

        # Sidebar: List
        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_vexpand(True)
        scrolled_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.list_box.add_css_class("navigation-sidebar")
        self.list_box.set_filter_func(self._filter_secret_row)
        self.list_box.connect("row-selected", self._on_secret_selected)
        scrolled_list.set_child(self.list_box)
        self.sidebar_stack.add_named(scrolled_list, "list")

        # Sidebar: Empty
        self.sidebar_empty = Adw.StatusPage(
            title=_("No secrets"),
            description=self._get_empty_text(),
            icon_name="dialog-password-symbolic",
        )
        self.create_first_btn = Gtk.Button(label=_("+ Create first secret"))
        self.create_first_btn.add_css_class("pill")
        self.create_first_btn.add_css_class("suggested-action")
        self.create_first_btn.connect("clicked", lambda _: self._on_create_secret_clicked())
        self.sidebar_empty.set_child(self.create_first_btn)
        self.sidebar_stack.add_named(self.sidebar_empty, "empty")

        # Sidebar: Error
        self.sidebar_error = Adw.StatusPage(
            title=_("Connection error"),
            description=self._get_error_text(),
            icon_name="dialog-error-symbolic",
        )
        self.retry_btn = Gtk.Button(label=_("Retry"))
        self.retry_btn.add_css_class("pill")
        self.retry_btn.add_css_class("suggested-action")
        self.retry_btn.connect("clicked", lambda _: self._load_secrets_async())
        self.sidebar_error.set_child(self.retry_btn)
        self.sidebar_stack.add_named(self.sidebar_error, "error")

        paned.set_start_child(sidebar_box)

        # Right: Detail Area
        self.detail_stack = Gtk.Stack()
        self.detail_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        paned.set_end_child(self.detail_stack)

        # Detail: Placeholder when no secret is selected
        self.placeholder_page = Adw.StatusPage(
            title=_("No secret selected"),
            description=_("Select a secret from the sidebar to inspect its configuration, versions, and payload."),
            icon_name="dialog-password-symbolic",
        )
        self.detail_stack.add_named(self.placeholder_page, "placeholder")

        # Detail: Content View
        self.detail_scroll = Gtk.ScrolledWindow()
        self.detail_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.detail_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.detail_container.set_margin_top(20)
        self.detail_container.set_margin_bottom(24)
        self.detail_container.set_margin_start(24)
        self.detail_container.set_margin_end(24)
        self.detail_scroll.set_child(self.detail_container)
        self.detail_stack.add_named(self.detail_scroll, "content")

        self._build_detail_widgets()
        self.detail_stack.set_visible_child_name("placeholder")

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
        title_box.append(self.add_version_btn)

        # Action button: Delete Secret
        self.delete_secret_btn = Gtk.Button(
            icon_name="user-trash-symbolic",
            tooltip_text=_("Permanently delete this secret"),
        )
        self.delete_secret_btn.add_css_class("destructive-action")
        self.delete_secret_btn.connect("clicked", lambda _: self._on_delete_secret_clicked())
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
        value_card.append(scrolled_text)

        self.payload_group.add(value_card)
        self.detail_container.append(self.payload_group)

        # Preferences Group 3: Versions History
        self.versions_group = Adw.PreferencesGroup(title=_("Version History"))
        self.versions_list_box = Gtk.ListBox()
        self.versions_list_box.add_css_class("boxed-list")
        self.versions_group.add(self.versions_list_box)
        self.detail_container.append(self.versions_group)

    # -------------------------------------------------------------
    # Provider & Context Switching
    # -------------------------------------------------------------
    def _on_provider_changed(self, dropdown: Gtk.DropDown, _param) -> None:
        """Handle selection changes in the provider dropdown switcher.

        Args:
            dropdown: Provider Gtk.DropDown widget.
            _param: GObject notify parameter.
        """
        idx = dropdown.get_selected()
        provider_keys = list(self.providers.keys())
        if 0 <= idx < len(provider_keys):
            target_key = provider_keys[idx]
            if target_key != self.active_provider.provider_id:
                self.active_provider = self.providers[target_key]
                self.selected_secret = None
                self.secrets = []
                self.current_versions = []
                self.current_payload = None
                self.detail_stack.set_visible_child_name("placeholder")
                self._update_header_and_tooltips()
                self._load_secrets_async()
                if target_key == "ansible" and not getattr(self.active_provider, "is_unlocked", True):
                    self._on_change_context_clicked(None)

    def _update_header_and_tooltips(self) -> None:
        """Update window title subtitle, buttons, tooltips, and state descriptions."""
        self.window_title.set_subtitle(self._get_context_subtitle())
        self.context_btn.set_tooltip_text(self._get_context_btn_tooltip())
        self.context_btn.set_icon_name(self._get_context_btn_icon())
        self.loading_label.set_label(self._get_loading_text())
        self.sidebar_empty.set_description(self._get_empty_text())
        self.sidebar_error.set_description(self._get_error_text())

    def _on_change_context_clicked(self, _btn: Optional[Gtk.Button]) -> None:
        """Polymorphically opens the context dialog for the currently active provider."""
        def on_context_confirmed() -> None:
            """Callback executed when the provider context configuration is confirmed."""
            self._update_header_and_tooltips()
            self._load_secrets_async()

        self.active_provider.open_context_dialog(self, on_context_confirmed)

    # -------------------------------------------------------------
    # Language Switching at Runtime
    # -------------------------------------------------------------
    def _toggle_language(self, _btn: Gtk.Button) -> None:
        """Toggle the application UI language between English and Spanish."""
        new_lang = "en" if get_current_language() == "es" else "es"
        set_language(new_lang)
        self.lang_btn.set_label(new_lang.upper())
        self._update_ui_texts()

    def _update_ui_texts(self) -> None:
        """Dynamically reloads all visible UI strings according to the active language."""
        self.set_title(_("Gossip"))
        self.window_title.set_title(_("Gossip"))
        self._update_header_and_tooltips()

        self.refresh_btn.set_tooltip_text(_("Reload secrets"))
        self.theme_btn.set_tooltip_text(_("Toggle light/dark theme"))
        self.about_btn.set_tooltip_text(_("About Gossip"))
        self.lang_btn.set_tooltip_text(_("Switch language (ES / EN)"))

        self.search_entry.set_placeholder_text(_("Search secrets..."))
        self.add_secret_btn.set_tooltip_text(_("Create new secret"))
        self.sidebar_empty.set_title(_("No secrets"))
        self.create_first_btn.set_label(_("+ Create first secret"))
        self.sidebar_error.set_title(_("Connection error"))
        self.retry_btn.set_label(_("Retry"))
        self.placeholder_page.set_title(_("No secret selected"))
        self.placeholder_page.set_description(
            _("Select a secret from the sidebar to inspect its configuration, versions, and payload.")
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
        self.copy_val_btn.set_label(_("Copy"))
        self.copy_val_btn.set_tooltip_text(_("Copy secret to clipboard"))
        self.versions_group.set_title(_("Version History"))

        if self.secrets:
            self._render_secret_list()
        if self.selected_secret:
            self._update_detail_labels()

    # -------------------------------------------------------------
    # Asynchronous Data Loading
    # -------------------------------------------------------------
    def _load_secrets_async(self) -> None:
        """Starts background thread to query secrets from active provider."""
        self.banner.set_revealed(False)
        self.sidebar_stack.set_visible_child_name("loading")
        self.sidebar_spinner.start()
        self.refresh_btn.set_sensitive(False)

        self.window_title.set_subtitle(self._get_context_subtitle())

        provider_id = self.active_provider.provider_id
        client = self.active_provider

        def worker() -> None:
            """Background worker thread fetching the list of secrets."""
            try:
                secrets = client.list_secrets()
                GLib.idle_add(self._on_secrets_loaded, secrets, None, provider_id)
            except Exception as exc:
                GLib.idle_add(self._on_secrets_loaded, [], str(exc), provider_id)

        threading.Thread(target=worker, daemon=True).start()

    def _on_secrets_loaded(
        self,
        secrets: List[SecretItem],
        error: Optional[str],
        provider_id: str,
    ) -> None:
        """Handle completion of the secrets query on the GTK main thread.

        Args:
            secrets: List of retrieved SecretItem instances.
            error: Error message string if the query failed, or None.
            provider_id: Provider identifier that initiated the request.
        """
        if provider_id != self.active_provider.provider_id:
            return  # Discard if user switched provider in the meantime

        self.sidebar_spinner.stop()
        self.refresh_btn.set_sensitive(True)

        if error:
            self.sidebar_error.set_description(error)
            self.sidebar_stack.set_visible_child_name("error")
            self.banner.set_title(error)
            self.banner.set_revealed(True)
            self.detail_stack.set_visible_child_name("placeholder")
            return

        self.secrets = secrets
        self._render_secret_list()

    def _render_secret_list(self) -> None:
        """Populate the sidebar list box with rows corresponding to loaded secrets."""
        while True:
            row = self.list_box.get_row_at_index(0)
            if row is None:
                break
            self.list_box.remove(row)

        if not self.secrets:
            self.sidebar_stack.set_visible_child_name("empty")
            self.detail_stack.set_visible_child_name("placeholder")
            return

        selected_row = None
        for secret in self.secrets:
            row = Adw.ActionRow(title=secret.secret_id)
            dt_str = secret.create_time.strftime("%Y-%m-%d") if secret.create_time else ""
            desc_part = f"{secret.description[:30]}... · " if secret.description else ""
            row.set_subtitle(f"{desc_part}{secret.replication_summary} · {dt_str}")

            if secret.labels:
                badge = Gtk.Label(label=f"{len(secret.labels)} {_('tags')}")
                badge.add_css_class("pill")
                badge.add_css_class("caption")
                row.add_suffix(badge)

            chevron = Gtk.Image.new_from_icon_name("go-next-symbolic")
            chevron.add_css_class("dim-label")
            row.add_suffix(chevron)

            row.secret_data = secret
            self.list_box.append(row)

            if self.selected_secret and secret.name == self.selected_secret.name:
                selected_row = row

        self.sidebar_stack.set_visible_child_name("list")

        if selected_row:
            self.list_box.select_row(selected_row)
        else:
            first_row = self.list_box.get_row_at_index(0)
            if first_row:
                self.list_box.select_row(first_row)

    # -------------------------------------------------------------
    # Secret Selection & Details
    # -------------------------------------------------------------
    def _on_secret_selected(self, _listbox: Gtk.ListBox, row: Optional[Adw.ActionRow]) -> None:
        """Handle user selection of a secret row in the sidebar.

        Args:
            _listbox: Sidebar Gtk.ListBox container.
            row: The selected Adw.ActionRow widget or None.
        """
        if not row or not hasattr(row, "secret_data"):
            return

        secret: SecretItem = row.secret_data
        self.selected_secret = secret
        self.detail_stack.set_visible_child_name("content")

        self.detail_title.set_label(secret.secret_id)
        self.detail_resource_name.set_label(secret.name)

        self._update_detail_labels()

        # Reset payload display
        self.current_payload = None
        self.is_payload_revealed = False
        self.text_buffer.set_text(_("Loading value..."))
        self.reveal_btn.set_icon_name("view-reveal-symbolic")
        self.copy_val_btn.set_sensitive(False)

        # Load versions async
        self._load_versions_async(secret.name)

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
                desc_title = _("Content Type / Description") if secret.provider == "azure" else _("Description")
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

        create_str = secret.create_time.strftime("%d/%m/%Y %H:%M:%S") if secret.create_time else _("Unknown")
        self.row_created.set_subtitle(create_str)

        if self.current_versions:
            self._render_versions_list(self.current_versions)

    def _load_versions_async(self, secret_name: str) -> None:
        """Start asynchronous background loading of all versions for a secret.

        Args:
            secret_name: Identifier or URI of the secret whose versions to list.
        """
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
        """Handle completion of the version history query on the GTK main thread.

        Args:
            versions: List of retrieved SecretVersionItem instances.
            error: Error message string if query failed, or None.
            secret_name: Name of the secret that was queried.
            provider_id: Provider identifier that initiated the query.
        """
        if provider_id != self.active_provider.provider_id:
            return
        if not self.selected_secret or self.selected_secret.name != secret_name:
            return

        self.payload_spinner.stop()

        if error:
            self._show_toast(f"Error: {error}")
            return

        self.current_versions = versions
        self._render_versions_list(versions)

        # Load payload of the selected version
        if versions:
            self._load_payload_async(versions[0].name)
        else:
            self.text_buffer.set_text(_("[No active versions]"))

    def _render_versions_list(self, versions: List[SecretVersionItem]) -> None:
        """Render rows for each secret version inside the versions list container.

        Args:
            versions: List of SecretVersionItem objects to display.
        """
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

                    pause_btn = Gtk.Button(
                        icon_name="media-playback-pause-symbolic",
                        tooltip_text=_("Disable version %s") % v.version_id,
                    )
                    pause_btn.add_css_class("flat")
                    pause_btn.connect("clicked", lambda _, ver=v: self._on_toggle_version_state(ver, enable=False))
                    action_box.append(pause_btn)

                    if provider.supports_version_destroy:
                        destroy_btn = Gtk.Button(
                            icon_name="edit-delete-symbolic",
                            tooltip_text=_("Permanently destroy version %s") % v.version_id,
                        )
                        destroy_btn.add_css_class("flat")
                        destroy_btn.add_css_class("destructive-action")
                        destroy_btn.connect("clicked", lambda _, ver=v: self._on_destroy_version_clicked(ver))
                        action_box.append(destroy_btn)

                elif v.state == "DISABLED":
                    state_label.add_css_class("warning")

                    play_btn = Gtk.Button(
                        icon_name="media-playback-start-symbolic",
                        tooltip_text=_("Enable version %s") % v.version_id,
                    )
                    play_btn.add_css_class("flat")
                    play_btn.connect("clicked", lambda _, ver=v: self._on_toggle_version_state(ver, enable=True))
                    action_box.append(play_btn)

                    if provider.supports_version_destroy:
                        destroy_btn = Gtk.Button(
                            icon_name="edit-delete-symbolic",
                            tooltip_text=_("Permanently destroy version %s") % v.version_id,
                        )
                        destroy_btn.add_css_class("flat")
                        destroy_btn.add_css_class("destructive-action")
                        destroy_btn.connect("clicked", lambda _, ver=v: self._on_destroy_version_clicked(ver))
                        action_box.append(destroy_btn)

                else:
                    state_label.add_css_class("error")
            else:
                # Providers without explicit enabled/disabled states (e.g. AWS version staging labels)
                if "AWSCURRENT" in v.stages:
                    state_label.add_css_class("success")
                elif "AWSPREVIOUS" in v.stages:
                    state_label.add_css_class("warning")
                else:
                    state_label.add_css_class("caption")

            action_box.append(state_label)
            v_row.add_suffix(action_box)
            self.versions_list_box.append(v_row)

        # Update Dropdown
        dropdown_items = [f"{_('Version %s') % v.version_id} ({v.display_state})" for v in versions]
        if not dropdown_items:
            dropdown_items = ["latest"]

        string_list = Gtk.StringList.new(dropdown_items)
        self.version_dropdown.set_model(string_list)
        self.version_dropdown.set_selected(0)

    def _on_version_changed(self, dropdown: Gtk.DropDown, _param) -> None:
        """Handle selection change in the version dropdown.

        Args:
            dropdown: Version selector Gtk.DropDown widget.
            _param: GObject notify parameter.
        """
        idx = dropdown.get_selected()
        if 0 <= idx < len(self.current_versions):
            selected_v = self.current_versions[idx]
            self._load_payload_async(selected_v.name)

    def _load_payload_async(self, version_name: str) -> None:
        """Start asynchronous background loading of secret payload value.

        Args:
            version_name: Version resource name or URI.
        """
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
        """Handle completion of payload query on the GTK main thread.

        Args:
            payload: Decoded secret string value or None if failed.
            is_binary: True if payload was identified as binary data.
            error: Error message string if retrieval failed, or None.
            provider_id: Provider identifier that initiated the request.
        """
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
        """Toggle between masked dots and revealed plaintext for secret payload.

        Args:
            _btn: Triggering Gtk.Button widget.
        """
        self.is_payload_revealed = not self.is_payload_revealed
        self._render_payload_text()

    # -------------------------------------------------------------
    # Secret Lifecycle Actions: Create, New Version, Disable/Enable, Destroy, Delete
    # -------------------------------------------------------------
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

        show_create_secret_dialog(self, on_confirm, provider=self.current_provider)

    def _on_secret_created_success(self, secret_id: str) -> None:
        """Callback executed on GTK main thread after secret creation succeeds.

        Args:
            secret_id: Identifier of the newly created secret.
        """
        self._show_toast(_("Secret '%s' created successfully") % secret_id)
        self._load_secrets_async()

    def _on_add_version_clicked(self) -> None:
        """Opens dialog to add a new version to the selected secret."""
        if not self.selected_secret:
            return

        secret_id = self.selected_secret.secret_id
        secret_name = self.selected_secret.name
        client = self.active_provider

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

        show_add_version_dialog(self, secret_id, on_confirm)

    def _on_version_added_success(self) -> None:
        """Callback executed on GTK main thread after new version is added."""
        self._show_toast(_("New version added successfully"))
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    def _on_toggle_version_state(self, version: SecretVersionItem, enable: bool) -> None:
        """Enables or disables a version via the active provider.

        Args:
            version: Target SecretVersionItem instance.
            enable: True to enable, False to disable.
        """
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
        """Callback executed on GTK main thread after version state change succeeds.

        Args:
            version_id: Identifier of the updated version.
            enabled: New state flag.
        """
        msg = (_("Version %s enabled") if enabled else _("Version %s disabled")) % version_id
        self._show_toast(msg)
        if self.selected_secret:
            self._load_versions_async(self.selected_secret.name)

    def _on_destroy_version_clicked(self, version: SecretVersionItem) -> None:
        """Opens confirmation dialog to destroy a version via the active provider.

        Args:
            version: SecretVersionItem instance to destroy.
        """
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

        show_confirm_destroy_version_dialog(self, version.version_id, on_confirm)

    def _on_version_destroyed_success(self, version_id: str) -> None:
        """Callback executed on GTK main thread after version is destroyed.

        Args:
            version_id: Identifier of the destroyed version.
        """
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

        show_confirm_delete_secret_dialog(self, secret_id, on_confirm, provider=self.current_provider)

    def _on_secret_deleted_success(self, secret_id: str) -> None:
        """Callback executed on GTK main thread after secret deletion succeeds.

        Args:
            secret_id: Identifier of deleted secret.
        """
        self._show_toast(_("Secret '%s' permanently deleted") % secret_id)
        self.selected_secret = None
        self.detail_stack.set_visible_child_name("placeholder")
        self._load_secrets_async()

    # -------------------------------------------------------------
    # Clipboard & Search Actions
    # -------------------------------------------------------------
    def _on_copy_payload(self, _btn: Gtk.Button) -> None:
        """Copy active secret plaintext payload to system clipboard.

        Args:
            _btn: Triggering Gtk.Button widget.
        """
        if not self.current_payload:
            return
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.current_payload)
        self._show_toast(_("Secret copied to clipboard"))

    def _on_copy_resource_name(self, _btn: Gtk.Button) -> None:
        """Copy full resource name/URI to system clipboard.

        Args:
            _btn: Triggering Gtk.Button widget.
        """
        if not self.selected_secret:
            return
        clipboard = Gdk.Display.get_default().get_clipboard()
        clipboard.set(self.selected_secret.name)
        self._show_toast(_("Resource name copied"))

    def _show_toast(self, text: str) -> None:
        """Display transient in-app notification toast banner.

        Args:
            text: Message string to show in toast.
        """
        toast = Adw.Toast.new(text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        """Trigger filter evaluation when search box text changes.

        Args:
            _entry: Triggering Gtk.SearchEntry widget.
        """
        self.list_box.invalidate_filter()

    def _filter_secret_row(self, row: Adw.ActionRow) -> bool:
        """Determine whether a sidebar secret row matches current search query.

        Args:
            row: Adw.ActionRow representing a secret item.

        Returns:
            bool: True if row matches query or query is empty; False otherwise.
        """
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        if not hasattr(row, "secret_data"):
            return True
        secret: SecretItem = row.secret_data
        if query in secret.secret_id.lower():
            return True
        if secret.description and query in secret.description.lower():
            return True
        for k, v in secret.labels.items():
            if query in k.lower() or query in v.lower():
                return True
        return False

    def _toggle_theme(self, _btn: Gtk.Button) -> None:
        """Toggle between dark and light application color schemes.

        Args:
            _btn: Triggering Gtk.Button widget.
        """
        style_mgr = Adw.StyleManager.get_default()
        if style_mgr.get_dark():
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
