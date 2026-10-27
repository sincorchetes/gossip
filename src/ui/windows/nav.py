"""Navigation, theme, language, and context management mixin for MainWindow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import audit, state
from src.i18n import _, get_current_language, set_language
from src.readonly import is_locked, is_read_only, set_read_only
from src.ui.background import run_in_background
from src.ui.icons import resolve_icon_name
from src.ui.windows.base import WindowBase

if TYPE_CHECKING:
    pass


class WindowNavMixin(WindowBase):
    """Provides navigation, theme switching, language toggling, and context dispatch."""

    # Typing attributes present on MainWindow

    def _get_context_subtitle(self) -> str:
        """Retrieve contextual subtitle from the active provider."""
        subtitle = self.active_provider.context_subtitle
        return f"{subtitle} · {_('read-only')}" if is_read_only() else subtitle

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
        candidates = fallback_map.get(icon) or [
            icon,
            "network-server-symbolic",
            "folder-remote-symbolic",
            "dialog-password-symbolic",
        ]
        return resolve_icon_name(candidates, fallback=icon)

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
                self.state.switch_provider(target_key)
                self._render_payload_text()
                self.payload_spinner.stop()
                self.detail_stack.set_visible_child_name("placeholder")
                self._remember()
                self._update_header_and_tooltips()
                self._load_secrets_async()
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

    def _audit(self, action: str, secret: Optional[str] = None, **extra: object) -> None:
        """Record an event in the optional audit log (names only, never values)."""
        provider = self.active_provider
        audit.record(
            action, provider.provider_id, provider.context_subtitle, secret=secret, **extra
        )

    def _remember(self, context_changed: bool = False) -> None:
        """Persist the active provider and, when it was just changed, its context."""
        saved = state.load()
        contexts, recents = saved["contexts"], saved["recents"]
        if context_changed:
            context = self.active_provider.saved_context()
            contexts[self.active_provider.provider_id] = context
            recents = state.remember_recent(recents, self.active_provider.provider_id, context)
        state.save(self.active_provider.provider_id, contexts, recents)

    def _on_change_context_clicked(self, _btn: Optional[Gtk.Button]) -> None:
        """Polymorphically opens the context dialog for the currently active provider."""

        def on_context_confirmed() -> None:
            """Callback executed when the provider context configuration is confirmed."""
            self._remember(context_changed=True)
            self._update_header_and_tooltips()
            self._load_secrets_async()

        self.active_provider.open_context_dialog(self, on_context_confirmed)

    def _toggle_language(self, _btn: Gtk.Button) -> None:
        """Toggle the application UI language between English and Spanish."""
        was_error = self.sidebar_stack.get_visible_child_name() == "error"
        new_lang = "en" if get_current_language() == "es" else "es"
        set_language(new_lang)
        state.update_ui(language=new_lang)
        self.lang_btn.set_label(new_lang.upper())
        self._update_ui_texts()
        if was_error:
            self._load_secrets_async()

    def _toggle_theme(self, _btn: Gtk.Button) -> None:
        """Toggle between dark and light application color schemes."""
        style_mgr = Adw.StyleManager.get_default()
        if style_mgr.get_dark():
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            state.update_ui(theme="light")
        else:
            style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            state.update_ui(theme="dark")

    def _run_in_background(
        self,
        task: Callable[[], Any],
        on_done: Callable[[Any], object],
        on_error: Optional[Callable[[Exception], object]] = None,
    ) -> None:
        """Run a provider call off the GTK thread; by default a failure becomes a toast."""
        run_in_background(
            task,
            on_done,
            on_error or (lambda exc: self._show_toast(_("Error: {detail}").format(detail=exc))),
        )

    def _show_toast(self, text: str) -> None:
        """Display transient in-app notification toast banner."""
        toast = Adw.Toast.new(text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def _refresh_read_only_button(self) -> None:
        """Show the current read-only state on the header toggle."""
        active = is_read_only()
        self.read_only_btn.set_icon_name(
            resolve_icon_name(
                ["changes-prevent-symbolic", "system-lock-screen-symbolic"]
                if active
                else ["changes-allow-symbolic", "document-edit-symbolic"],
                fallback="changes-prevent-symbolic" if active else "changes-allow-symbolic",
            )
        )
        self.read_only_btn.set_sensitive(not is_locked())
        self.read_only_btn.set_tooltip_text(
            _("Read-only mode is locked: it was started with --read-only")
            if is_locked()
            else _("Read-only mode is on: click to allow changes")
            if active
            else _("Read-only mode is off: click to block creating, editing and deleting")
        )

    def _on_read_only_toggled(self, button: Gtk.ToggleButton) -> None:
        """Turn read-only mode on or off and update every control that can change data."""
        set_read_only(button.get_active())
        if button.get_active() != is_read_only():  # refused (locked): put the toggle back
            button.set_active(is_read_only())
            return
        writable = not is_read_only()
        for control in (
            self.add_secret_btn,
            self.create_first_btn,
            self.add_version_btn,
            self.delete_secret_btn,
        ):
            control.set_visible(writable)
        self._update_edit_button()
        self._populate_transfer_menu()
        if self.current_versions:
            self._render_versions_list(self.current_versions)
        self._refresh_read_only_button()
        self._update_header_and_tooltips()
        self._show_toast(
            _("Read-only mode enabled") if is_read_only() else _("Read-only mode disabled")
        )
