"""Keyboard shortcuts of the main window and the dialog that lists them."""

from __future__ import annotations

from typing import Callable, List, Tuple

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk

from src.i18n import _
from src.ui.windows.base import WindowBase


def shortcut_table() -> List[Tuple[str, str]]:
    """Accelerators and their (translated) descriptions, in the order they are listed."""
    return [
        ("<Primary>n", _("New secret")),
        ("<Primary>f", _("Search secrets")),
        ("F5", _("Reload secrets")),
        ("<Primary>r", _("Reload secrets")),
        ("<Primary><Shift>r", _("Show / hide the value")),
        ("<Primary><Shift>c", _("Copy the value")),
        ("<Primary>e", _("Edit labels and description")),
        ("<Primary>Delete", _("Delete the secret")),
        ("F1", _("Show the keyboard shortcuts")),
    ]


def _label(accel: str) -> str:
    """Platform-aware text for an accelerator (Ctrl on Linux and Windows, Cmd on macOS)."""
    trigger = Gtk.ShortcutTrigger.parse_string(accel)
    display = Gdk.Display.get_default()
    return trigger.to_label(display) if trigger and display else accel


class WindowShortcutsMixin(WindowBase):
    """Registers the window-wide keyboard shortcuts."""

    def _shortcut_actions(self) -> List[Tuple[str, Callable[[], object]]]:
        """Accelerator and handler pairs (Ctrl+F is registered by the sidebar)."""
        return [
            ("<Primary>n", lambda: self._on_create_secret_clicked()),
            ("F5", lambda: self._load_secrets_async()),
            ("<Primary>r", lambda: self._load_secrets_async()),
            ("<Primary><Shift>r", lambda: self._on_toggle_reveal(None)),
            ("<Primary><Shift>c", lambda: self._on_copy_payload(None)),
            ("<Primary>e", lambda: self._on_edit_metadata_clicked()),
            ("<Primary>Delete", lambda: self._on_delete_secret_clicked()),
            ("F1", lambda: self._show_shortcuts_dialog()),
        ]

    def _setup_shortcuts(self) -> None:
        """Install the global shortcuts on the window."""
        controller = Gtk.ShortcutController()
        controller.set_scope(Gtk.ShortcutScope.GLOBAL)
        for accel, handler in self._shortcut_actions():
            controller.add_shortcut(
                Gtk.Shortcut.new(
                    Gtk.ShortcutTrigger.parse_string(accel),
                    Gtk.CallbackAction.new(lambda *_args, h=handler: bool(h() or True)),
                )
            )
        self.add_controller(controller)
        self._shortcut_controller = controller

    def _show_shortcuts_dialog(self) -> Adw.MessageDialog:
        """List the keyboard shortcuts."""
        body = "\n".join(f"{_label(accel):<18}{text}" for accel, text in shortcut_table())
        dialog = Adw.MessageDialog(
            transient_for=self,
            heading=_("Keyboard shortcuts"),
            body=body,
        )
        dialog.add_response("close", _("Close"))
        dialog.set_close_response("close")
        dialog.present()
        return dialog
