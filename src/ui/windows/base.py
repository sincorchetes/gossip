"""What the window mixins share: the widgets, the state and the methods they call on each other.

Each mixin of MainWindow (navigation, sidebar, detail, versions, actions, transfer, idle lock...)
needs things another mixin or the window itself creates. They are declared once here, so every
mixin sees the same typed contract instead of repeating annotations and silencing the type
checker. Only annotations and type-checking stubs live here: nothing is defined at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk

from src.models import SecretItem, SecretVersionItem
from src.ui.dialogs.factory import DialogFactory
from src.ui.windows.state import WindowState

if TYPE_CHECKING:
    from src.providers import BaseSecretProvider


class WindowBase:
    """Shared declarations for the MainWindow mixins (plain class; MainWindow adds the GTK base)."""

    # -- state: one plain object; the attributes below read and write it
    state: WindowState
    dialogs: DialogFactory

    @property
    def providers(self) -> Dict[str, BaseSecretProvider]:
        return self.state.providers

    @property
    def active_provider(self) -> BaseSecretProvider:
        return self.state.active_provider

    @active_provider.setter
    def active_provider(self, value: BaseSecretProvider) -> None:
        self.state.active_provider = value

    @property
    def secrets(self) -> List[SecretItem]:
        return self.state.secrets

    @secrets.setter
    def secrets(self, value: List[SecretItem]) -> None:
        self.state.secrets = value

    @property
    def selected_secret(self) -> Optional[SecretItem]:
        return self.state.selected_secret

    @selected_secret.setter
    def selected_secret(self, value: Optional[SecretItem]) -> None:
        self.state.selected_secret = value

    @property
    def current_versions(self) -> List[SecretVersionItem]:
        return self.state.current_versions

    @current_versions.setter
    def current_versions(self, value: List[SecretVersionItem]) -> None:
        self.state.current_versions = value

    @property
    def current_payload(self) -> Optional[str]:
        return self.state.current_payload

    @current_payload.setter
    def current_payload(self, value: Optional[str]) -> None:
        self.state.current_payload = value

    @property
    def is_payload_revealed(self) -> bool:
        return self.state.is_payload_revealed

    @is_payload_revealed.setter
    def is_payload_revealed(self, value: bool) -> None:
        self.state.is_payload_revealed = value

    @property
    def _payload_request_id(self) -> int:
        return self.state.payload_request_id

    @property
    def _payload_pending(self) -> Optional[str]:
        return self.state.payload_pending

    @_payload_pending.setter
    def _payload_pending(self, value: Optional[str]) -> None:
        self.state.payload_pending = value

    # -- header bar
    toast_overlay: Adw.ToastOverlay
    window_title: Adw.WindowTitle
    provider_dropdown: Gtk.DropDown
    context_btn: Gtk.Button
    refresh_btn: Gtk.Button
    lang_btn: Gtk.Button
    theme_btn: Gtk.Button
    about_btn: Gtk.Button
    read_only_btn: Gtk.ToggleButton
    transfer_btn: Gtk.MenuButton
    transfer_menu: Gio.Menu
    banner: Adw.Banner

    # -- sidebar
    search_entry: Gtk.SearchEntry
    no_results_page: Adw.StatusPage
    add_secret_btn: Gtk.Button
    sidebar_stack: Gtk.Stack
    sidebar_spinner: Gtk.Spinner
    loading_label: Gtk.Label
    list_view: Gtk.ListView
    list_store: Gio.ListStore
    list_selection: Gtk.SingleSelection
    list_stack: Gtk.Stack
    sidebar_empty: Adw.StatusPage
    create_first_btn: Gtk.Button
    sidebar_error: Adw.StatusPage
    retry_btn: Gtk.Button

    # -- detail pane
    detail_stack: Gtk.Stack
    placeholder_page: Adw.StatusPage
    detail_scroll: Gtk.ScrolledWindow
    detail_container: Gtk.Box
    detail_title: Gtk.Label
    detail_resource_name: Gtk.Label
    copy_name_btn: Gtk.Button
    add_version_btn: Gtk.Button
    edit_meta_btn: Gtk.Button
    delete_secret_btn: Gtk.Button
    info_group: Adw.PreferencesGroup
    row_description: Adw.ActionRow
    row_created: Adw.ActionRow
    row_replication: Adw.ActionRow
    row_labels: Adw.ActionRow
    payload_group: Adw.PreferencesGroup
    row_version: Adw.ActionRow
    version_dropdown: Gtk.DropDown
    val_title: Gtk.Label
    payload_spinner: Gtk.Spinner
    reveal_btn: Gtk.Button
    compare_btn: Gtk.Button
    compare_other_btn: Gtk.Button
    copy_val_btn: Gtk.Button
    table_btn: Gtk.ToggleButton
    table_list: Gtk.ListBox
    value_stack: Gtk.Stack
    text_view: Gtk.TextView
    text_buffer: Gtk.TextBuffer
    versions_group: Adw.PreferencesGroup
    versions_list_box: Gtk.ListBox

    if TYPE_CHECKING:
        # What the mixins use from Adw.ApplicationWindow, which has no type stubs
        def add_controller(self, controller: Any) -> None: ...
        def add_action(self, action: Any) -> None: ...
        def lookup_action(self, name: str) -> Any: ...
        def set_title(self, title: str) -> None: ...
        def set_content(self, content: Any) -> None: ...
        def is_maximized(self) -> bool: ...
        def get_width(self) -> int: ...
        def get_height(self) -> int: ...
        def connect(self, signal: str, handler: Any, *args: Any) -> int: ...

        # Methods that live in one mixin and are called from another (or from the window).
        # -- navigation
        def _show_toast(self, text: str) -> None: ...
        def _run_in_background(
            self,
            task: Callable[[], Any],
            on_done: Callable[[Any], object],
            on_error: Optional[Callable[[Exception], object]] = None,
        ) -> None: ...
        def _audit(self, action: str, secret: Optional[str] = None, **extra: Any) -> None: ...
        def _get_context_subtitle(self) -> str: ...
        def _get_context_btn_tooltip(self) -> str: ...
        def _get_context_btn_icon(self) -> str: ...
        def _get_loading_text(self) -> str: ...
        def _get_empty_text(self) -> str: ...
        def _get_error_text(self) -> str: ...
        def _update_header_and_tooltips(self) -> None: ...
        def _refresh_read_only_button(self) -> None: ...
        def _on_change_context_clicked(self, _btn: Optional[Gtk.Button]) -> None: ...
        def _on_provider_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None: ...
        def _on_read_only_toggled(self, button: Gtk.ToggleButton) -> None: ...
        def _toggle_language(self, _btn: Gtk.Button) -> None: ...
        def _toggle_theme(self, _btn: Gtk.Button) -> None: ...
        # -- builder, sidebar, detail, transfer
        def _update_ui_texts(self) -> None: ...
        def _build_sidebar_widgets(self) -> Gtk.Box: ...
        def _build_detail_widgets(self) -> None: ...
        def _build_transfer_menu(self) -> Gtk.MenuButton: ...
        def _populate_transfer_menu(self) -> None: ...
        def _update_sidebar_texts(self) -> None: ...
        def _update_detail_texts(self) -> None: ...
        def _update_transfer_texts(self) -> None: ...
        def _load_secrets_async(self) -> None: ...
        def _render_secret_list(self) -> None: ...
        # -- versions and payload
        def _load_versions_async(self, secret_name: str) -> None: ...
        def _render_versions_list(self, versions: List[SecretVersionItem]) -> None: ...
        def _update_detail_labels(self) -> None: ...
        def _update_edit_button(self) -> None: ...
        def _reset_payload(self) -> None: ...
        def _request_payload(self, intent: str) -> None: ...
        def _render_payload_text(self) -> None: ...
        def _on_version_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None: ...
        def _on_table_toggled(self, button: Gtk.ToggleButton) -> None: ...
        def _on_toggle_reveal(self, _btn: Optional[Gtk.Button]) -> None: ...
        def _on_compare_versions(self, _btn: Gtk.Button) -> None: ...
        def _on_compare_with_other(self, _btn: Gtk.Button) -> None: ...
        # -- actions
        def _on_create_secret_clicked(self) -> None: ...
        def _on_add_version_clicked(self) -> None: ...
        def _on_edit_metadata_clicked(self) -> None: ...
        def _on_delete_secret_clicked(self) -> None: ...
        def _on_restore_version_clicked(self, version: SecretVersionItem) -> None: ...
        def _on_toggle_version_state(self, version: SecretVersionItem, enable: bool) -> None: ...
        def _on_destroy_version_clicked(self, version: SecretVersionItem) -> None: ...
        def _on_copy_payload(self, _btn: Optional[Gtk.Button]) -> None: ...
        def _on_copy_resource_name(self, _btn: Gtk.Button) -> None: ...
        def _on_copy_key(self, key: str, value: str) -> None: ...
        def _copy_payload_to_clipboard(
            self, text: str, audit_field: Optional[str] = None
        ) -> None: ...
        def _cancel_clipboard_clear(self) -> None: ...
        def is_active(self) -> bool: ...
        def _arm_reveal_timer(self) -> None: ...
        def _cancel_reveal_timer(self) -> None: ...
