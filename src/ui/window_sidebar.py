"""Sidebar widget construction, secrets listing, filtering, and async loading mixin."""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.models import SecretItem

if TYPE_CHECKING:
    from src.providers import BaseSecretProvider


class WindowSidebarMixin:
    """Constructs sidebar UI widgets and manages secrets list loading, filtering, and rendering."""

    # UI widget references
    search_entry: Gtk.SearchEntry
    add_secret_btn: Gtk.Button
    sidebar_stack: Gtk.Stack
    sidebar_spinner: Gtk.Spinner
    loading_label: Gtk.Label
    list_box: Gtk.ListBox
    sidebar_empty: Adw.StatusPage
    create_first_btn: Gtk.Button
    sidebar_error: Adw.StatusPage
    retry_btn: Gtk.Button
    banner: Adw.Banner
    refresh_btn: Gtk.Button
    window_title: Adw.WindowTitle
    detail_stack: Gtk.Stack
    detail_title: Gtk.Label
    detail_resource_name: Gtk.Label
    text_buffer: Gtk.TextBuffer
    reveal_btn: Gtk.Button
    copy_val_btn: Gtk.Button

    # State attributes
    active_provider: BaseSecretProvider
    secrets: List[SecretItem]
    selected_secret: Optional[SecretItem]
    current_payload: Optional[str]
    is_payload_revealed: bool

    def _build_sidebar_widgets(self) -> Gtk.Box:
        """Construct sidebar layout and its child widgets."""
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar_box.set_margin_top(8)
        sidebar_box.set_margin_bottom(8)
        sidebar_box.set_margin_start(8)
        sidebar_box.set_margin_end(8)
        sidebar_box.set_size_request(300, -1)

        # Search Bar + "+ Create secret" Button
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
        self.add_secret_btn.connect("clicked", lambda _: self._on_create_secret_clicked())  # type: ignore[attr-defined]
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
        self.loading_label = Gtk.Label(label=self._get_loading_text())  # type: ignore[attr-defined]
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
            description=self._get_empty_text(),  # type: ignore[attr-defined]
            icon_name="dialog-password-symbolic",
        )
        self.create_first_btn = Gtk.Button(label=_("+ Create first secret"))
        self.create_first_btn.add_css_class("pill")
        self.create_first_btn.add_css_class("suggested-action")
        self.create_first_btn.connect("clicked", lambda _: self._on_create_secret_clicked())  # type: ignore[attr-defined]
        self.sidebar_empty.set_child(self.create_first_btn)
        self.sidebar_stack.add_named(self.sidebar_empty, "empty")

        # Sidebar: Error
        self.sidebar_error = Adw.StatusPage(
            title=_("Connection error"),
            description=self._get_error_text(),  # type: ignore[attr-defined]
            icon_name="dialog-error-symbolic",
        )
        self.retry_btn = Gtk.Button(label=_("Retry"))
        self.retry_btn.add_css_class("pill")
        self.retry_btn.add_css_class("suggested-action")
        self.retry_btn.connect("clicked", lambda _: self._load_secrets_async())
        self.sidebar_error.set_child(self.retry_btn)
        self.sidebar_stack.add_named(self.sidebar_error, "error")

        return sidebar_box

    def _update_sidebar_texts(self) -> None:
        """Update localized texts for sidebar widgets."""
        self.search_entry.set_placeholder_text(_("Search secrets..."))
        self.add_secret_btn.set_tooltip_text(_("Create new secret"))
        self.sidebar_empty.set_title(_("No secrets"))
        self.create_first_btn.set_label(_("+ Create first secret"))
        self.sidebar_error.set_title(_("Connection error"))
        self.retry_btn.set_label(_("Retry"))

    def _load_secrets_async(self) -> None:
        """Starts background thread to query secrets from active provider."""
        self.banner.set_revealed(False)
        self.sidebar_stack.set_visible_child_name("loading")
        self.sidebar_spinner.start()
        self.refresh_btn.set_sensitive(False)

        self.window_title.set_subtitle(self._get_context_subtitle())  # type: ignore[attr-defined]

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
        """Handle completion of the secrets query on the GTK main thread."""
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

            row.secret_data = secret  # type: ignore[attr-defined]
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

    def _on_secret_selected(self, _listbox: Gtk.ListBox, row: Optional[Adw.ActionRow]) -> None:
        """Handle user selection of a secret row in the sidebar."""
        if not row or not hasattr(row, "secret_data"):
            return

        secret: SecretItem = row.secret_data  # type: ignore[attr-defined]
        self.selected_secret = secret
        self.detail_stack.set_visible_child_name("content")

        self.detail_title.set_label(secret.secret_id)
        self.detail_resource_name.set_label(secret.name)

        self._update_detail_labels()  # type: ignore[attr-defined]

        # Reset payload display
        self.current_payload = None
        self.is_payload_revealed = False
        self.text_buffer.set_text(_("Loading value..."))
        self.reveal_btn.set_icon_name("view-reveal-symbolic")
        self.copy_val_btn.set_sensitive(False)

        # Load versions async
        self._load_versions_async(secret.name)  # type: ignore[attr-defined]

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        """Trigger filter evaluation when search box text changes."""
        self.list_box.invalidate_filter()

    def _filter_secret_row(self, row: Adw.ActionRow) -> bool:
        """Determine whether a sidebar secret row matches current search query."""
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        if not hasattr(row, "secret_data"):
            return True
        secret: SecretItem = row.secret_data  # type: ignore[attr-defined]
        if query in secret.secret_id.lower():
            return True
        if secret.description and query in secret.description.lower():
            return True
        for k, v in secret.labels.items():
            if query in k.lower() or query in v.lower():
                return True
        return False
