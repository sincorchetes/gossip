"""Sidebar widget construction, secrets listing, filtering, and async loading mixin."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, GObject, Gtk

from src import tree
from src.age import age_days, is_stale
from src.i18n import _
from src.models import SecretItem
from src.readonly import is_read_only
from src.ui.windows.base import WindowBase

if TYPE_CHECKING:
    pass


class NodeObject(GObject.Object):
    """Wraps a tree node so it can live in a Gio.ListStore."""

    def __init__(self, node: tree.Node) -> None:
        super().__init__()
        self.node = node


class WindowSidebarMixin(WindowBase):
    """Constructs sidebar UI widgets and manages secrets list loading, filtering, and rendering."""

    # UI widget references

    # State attributes

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
        self.search_entry.connect("stop-search", self._on_search_stopped)
        self.search_entry.set_tooltip_text(self._get_search_help())
        self.search_entry.set_hexpand(True)
        search_box.append(self.search_entry)

        self.add_secret_btn = Gtk.Button(
            icon_name="list-add-symbolic",
            tooltip_text=_("Create new secret"),
        )
        self.add_secret_btn.add_css_class("suggested-action")
        self.add_secret_btn.connect("clicked", lambda _: self._on_create_secret_clicked())
        self.add_secret_btn.set_visible(not is_read_only())
        search_box.append(self.add_secret_btn)
        sidebar_box.append(search_box)

        # Ctrl+F (Cmd+F on macOS) focuses the search box from anywhere in the window
        focus_search = Gtk.Shortcut.new(
            Gtk.ShortcutTrigger.parse_string("<Primary>f"),
            Gtk.CallbackAction.new(lambda *_args: self._focus_search()),
        )
        shortcuts = Gtk.ShortcutController()
        shortcuts.set_scope(Gtk.ShortcutScope.GLOBAL)
        shortcuts.add_shortcut(focus_search)
        self.add_controller(shortcuts)

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
        self.list_store = Gio.ListStore.new(NodeObject)
        self.list_selection = Gtk.SingleSelection.new(self.list_store)
        self.list_selection.set_autoselect(False)
        self.list_selection.set_can_unselect(True)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._setup_row)
        factory.connect("bind", self._bind_row)
        self.list_view = Gtk.ListView.new(self.list_selection, factory)
        self.list_view.add_css_class("navigation-sidebar")
        self.list_view.set_single_click_activate(True)
        self.list_view.connect("activate", self._on_row_activated)
        self.list_selection.connect("notify::selected-item", self._on_node_selected)
        self._expanded: set = set()
        self._expanded_for: Optional[str] = None
        self._rebuilding = False
        self.no_results_page = Adw.StatusPage(
            title=_("No matching secrets"),
            description=_("Try another search or filter by label, e.g. label:env=prod"),
            icon_name="system-search-symbolic",
        )
        scrolled_list.set_child(self.list_view)
        self.list_scroll = scrolled_list
        self.list_stack = Gtk.Stack()
        self.list_stack.add_named(scrolled_list, "results")
        self.list_stack.add_named(self.no_results_page, "none")
        self.sidebar_stack.add_named(self.list_stack, "list")

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
        self.create_first_btn.set_visible(not is_read_only())
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

        return sidebar_box

    def _update_sidebar_texts(self) -> None:
        """Update localized texts for sidebar widgets."""
        self.search_entry.set_placeholder_text(_("Search secrets..."))
        self.search_entry.set_tooltip_text(self._get_search_help())
        self.no_results_page.set_title(_("No matching secrets"))
        self.no_results_page.set_description(
            _("Try another search or filter by label, e.g. label:env=prod")
        )
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

        self.window_title.set_subtitle(self._get_context_subtitle())

        provider_id = self.active_provider.provider_id
        client = self.active_provider

        self._run_in_background(
            client.list_secrets,
            lambda secrets: self._on_secrets_loaded(secrets, None, provider_id),
            lambda exc: self._on_secrets_loaded([], str(exc), provider_id),
        )

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

    def _setup_row(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        """Create the widgets of one row; they are reused as the list scrolls."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.set_margin_top(6)
        row.set_margin_bottom(6)
        row.set_margin_start(8)
        row.set_margin_end(8)
        row.indent = Gtk.Box()
        row.icon = Gtk.Image()
        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        texts.set_hexpand(True)
        row.title = Gtk.Label(xalign=0, ellipsize=3)
        row.subtitle = Gtk.Label(xalign=0, ellipsize=3)
        row.subtitle.add_css_class("caption")
        row.subtitle.add_css_class("dim-label")
        texts.append(row.title)
        texts.append(row.subtitle)
        row.badges = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        for widget in (row.indent, row.icon, texts, row.badges):
            row.append(widget)
        item.set_child(row)

    def _bind_row(self, _factory: Gtk.SignalListItemFactory, item: Gtk.ListItem) -> None:
        """Fill a row with the node it now shows."""
        node: tree.Node = item.get_item().node
        row = item.get_child()
        row.indent.set_size_request(node.depth * 16, -1)
        while (badge := row.badges.get_first_child()) is not None:
            row.badges.remove(badge)
        item.set_selectable(node.kind == tree.SECRET)
        row.title.set_label(node.title)
        if node.kind == tree.FOLDER:
            row.icon.set_from_icon_name(
                "folder-open-symbolic" if node.expanded else "folder-symbolic"
            )
            row.subtitle.set_visible(False)
            row.title.add_css_class("heading")
            count = Gtk.Label(label=str(node.count))
            count.add_css_class("dim-label")
            row.badges.append(count)
            return
        secret = node.secret
        assert secret is not None
        row.title.remove_css_class("heading")
        row.icon.set_from_icon_name("dialog-password-symbolic")
        dt_str = secret.create_time.strftime("%Y-%m-%d") if secret.create_time else ""
        desc_part = f"{secret.description[:30]}... · " if secret.description else ""
        row.subtitle.set_label(f"{desc_part}{secret.replication_summary} · {dt_str}")
        row.subtitle.set_visible(True)
        if secret.labels:
            badge = Gtk.Label(label=f"{len(secret.labels)} {_('tags')}")
            badge.add_css_class("pill")
            badge.add_css_class("caption")
            row.badges.append(badge)
        if is_stale(secret):
            days = age_days(secret) or 0
            stale = Gtk.Label(label=_("%d d") % days)
            stale.add_css_class("pill")
            stale.add_css_class("warning")
            stale.set_tooltip_text(_("Not changed for %d days; consider rotating it") % days)
            row.badges.append(stale)

    def _render_secret_list(self) -> None:
        """Show the loaded secrets as a tree (or a flat list) in the sidebar."""
        if not self.secrets:
            self._set_nodes([])
            self.sidebar_stack.set_visible_child_name("empty")
            self.detail_stack.set_visible_child_name("placeholder")
            return

        provider_id = self.active_provider.provider_id
        if self._expanded_for != provider_id:
            self._expanded = tree.default_expanded(self.secrets)
            self._expanded_for = provider_id
        self.sidebar_stack.set_visible_child_name("list")
        self._rebuild_nodes(select_first=True)

    def _rebuild_nodes(self, select_first: bool = False) -> None:
        """Recompute the visible rows from the secrets, open folders and search text."""
        nodes = tree.build_nodes(self.secrets, self._expanded, self.search_entry.get_text())
        self._set_nodes(nodes)
        self.list_stack.set_visible_child_name("results" if nodes or not self.secrets else "none")

        # Keep the current secret selected when it is still visible
        index = next(
            (
                i
                for i, node in enumerate(nodes)
                if node.secret
                and self.selected_secret
                and node.secret.name == self.selected_secret.name
            ),
            None,
        )
        if index is None and select_first and not self.selected_secret:
            index = next((i for i, node in enumerate(nodes) if node.secret), None)
        if index is not None and self.list_selection.get_selected() != index:
            self.list_selection.set_selected(index)

    def _set_nodes(self, nodes: List[tree.Node]) -> None:
        """Replace the rows without announcing the transient selection changes."""
        self._rebuilding = True
        try:
            adjustment = self.list_scroll.get_vadjustment()
            position = adjustment.get_value()
            self.list_store.splice(0, self.list_store.get_n_items(), [NodeObject(n) for n in nodes])
            GLib.idle_add(adjustment.set_value, position)
        finally:
            self._rebuilding = False

    def _on_row_activated(self, _view: Gtk.ListView, position: int) -> None:
        """Open or close a folder when it is clicked."""
        item = self.list_store.get_item(position)
        node = item.node if item is not None else None
        if node is None or node.kind != tree.FOLDER:
            return
        if node.path in self._expanded:
            self._expanded.discard(node.path)
        else:
            self._expanded.add(node.path)
        self._rebuild_nodes()

    def _on_node_selected(self, selection: Gtk.SingleSelection, _param: object) -> None:
        """Show the secret that was selected in the list."""
        if self._rebuilding:
            return
        item = selection.get_selected_item()
        node = item.node if item is not None else None
        if node is not None and node.secret is not None:
            self._on_secret_selected(node.secret)

    def _on_secret_selected(self, secret: Optional[SecretItem]) -> None:
        """Handle the user's choice of a secret in the sidebar."""
        if secret is None:
            return
        self.state.select_secret(secret)
        self.detail_stack.set_visible_child_name("content")

        self.detail_title.set_label(secret.secret_id)
        self.detail_resource_name.set_label(secret.name)

        self._update_detail_labels()

        # The previous secret's value is already forgotten; the new one is fetched on demand
        self.payload_spinner.stop()
        self._render_payload_text()
        self.copy_val_btn.set_sensitive(False)

        # Load versions async
        self._load_versions_async(secret.name)

    @staticmethod
    def _get_search_help() -> str:
        """Localized tooltip explaining the search syntax."""
        return _(
            "Search by name, description or label. "
            "Use label:key=value to filter by label and -word to exclude."
        )

    def _focus_search(self) -> bool:
        """Move keyboard focus to the search box (Ctrl+F, Cmd+F on macOS)."""
        self.search_entry.grab_focus()
        return True

    def _on_search_stopped(self, entry: Gtk.SearchEntry) -> None:
        """Clear the search text when the user presses Escape in the search box."""
        entry.set_text("")

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        """Re-filter the list when the search box text changes."""
        self._rebuild_nodes()
