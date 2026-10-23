"""Navigation, theme, language, and context management mixin for MainWindow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import get_current_language, set_language
from src.ui.icons import resolve_icon_name

if TYPE_CHECKING:
    from src.providers import BaseSecretProvider


class WindowNavMixin:
    """Provides navigation, theme switching, language toggling, and context dispatch."""

    # Typing attributes present on MainWindow
    active_provider: BaseSecretProvider
    providers: dict[str, BaseSecretProvider]
    toast_overlay: Adw.ToastOverlay
    window_title: Adw.WindowTitle
    context_btn: Gtk.Button
    loading_label: Gtk.Label
    sidebar_empty: Adw.StatusPage
    sidebar_error: Adw.StatusPage
    sidebar_stack: Gtk.Stack
    lang_btn: Gtk.Button

    def _get_context_subtitle(self) -> str:
        """Retrieve contextual subtitle from the active provider."""
        return self.active_provider.context_subtitle

    def _get_context_btn_tooltip(self) -> str:
        """Retrieve tooltip text for the context switcher button."""
        return self.active_provider.context_btn_tooltip

    def _get_context_btn_icon(self) -> str:
        """Retrieve icon name for the active provider, resolving fallback icons if missing."""
        icon = self.active_provider.icon_name
        fallback_map = {
            "preferences-system-symbolic": [
                "preferences-system-symbolic",
                "network-server-symbolic",
                "system-run-symbolic",
            ],
            "security-high-symbolic": [
                "security-high-symbolic",
                "changes-prevent-symbolic",
                "dialog-password-symbolic",
            ],
        }
        if icon in fallback_map:
            return resolve_icon_name(fallback_map[icon], fallback=icon)
        return icon

    def _get_loading_text(self) -> str:
        """Retrieve loading text for the active provider."""
        return self.active_provider.loading_message

    def _get_empty_text(self) -> str:
        """Retrieve empty state message for the active provider."""
        return self.active_provider.empty_message

    def _get_error_text(self) -> str:
        """Retrieve error state message for the active provider."""
        return self.active_provider.error_message

    def _on_provider_changed(self, dropdown: Gtk.DropDown, _param) -> None:
        """Handle selection changes in the provider dropdown switcher."""
        idx = dropdown.get_selected()
        provider_keys = list(self.providers.keys())
        if 0 <= idx < len(provider_keys):
            target_key = provider_keys[idx]
            if target_key != self.active_provider.provider_id:
                self.active_provider = self.providers[target_key]
                self.selected_secret = None  # type: ignore[attr-defined]
                self.secrets = []  # type: ignore[attr-defined]
                self.current_versions = []  # type: ignore[attr-defined]
                self.current_payload = None  # type: ignore[attr-defined]
                self.detail_stack.set_visible_child_name("placeholder")  # type: ignore[attr-defined]
                self._update_header_and_tooltips()
                self._load_secrets_async()  # type: ignore[attr-defined]
                if target_key == "ansible" and not getattr(
                    self.active_provider, "is_unlocked", True
                ):
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
            self._load_secrets_async()  # type: ignore[attr-defined]

        self.active_provider.open_context_dialog(self, on_context_confirmed)

    def _toggle_language(self, _btn: Gtk.Button) -> None:
        """Toggle the application UI language between English and Spanish."""
        was_error = self.sidebar_stack.get_visible_child_name() == "error"
        new_lang = "en" if get_current_language() == "es" else "es"
        set_language(new_lang)
        self.lang_btn.set_label(new_lang.upper())
        self._update_ui_texts()  # type: ignore[attr-defined]
        if was_error:
            self._load_secrets_async()  # type: ignore[attr-defined]

    def _toggle_theme(self, _btn: Gtk.Button) -> None:
        """Toggle between dark and light application color schemes."""
        style_mgr = Adw.StyleManager.get_default()
        if style_mgr.get_dark():
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    def _show_toast(self, text: str) -> None:
        """Display transient in-app notification toast banner."""
        toast = Adw.Toast.new(text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)
