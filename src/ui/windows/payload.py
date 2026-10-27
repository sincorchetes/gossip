"""Reveal, copy and table view of the selected secret's value."""

from __future__ import annotations

from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.payload_view import parse_key_values
from src.ui.a11y import label_icon_buttons
from src.ui.windows.base import WindowBase
from src.ui.windows.state import FAILED, IGNORED, REVEAL

_PAYLOAD_PLACEHOLDER = "•" * 8


class WindowPayloadMixin(WindowBase):
    """Fetches the value on demand and shows it masked, revealed or as a table."""

    def _reset_payload(self) -> None:
        """Forget the loaded value and invalidate in-flight requests so late replies are ignored."""
        self.state.forget_payload()
        self.payload_spinner.stop()
        self._render_payload_text()

    def _request_payload(self, intent: str) -> None:
        """Fetch the selected version's value because the user asked to reveal or copy it.

        Args:
            intent: What to do once the value arrives: "reveal" or "copy".
        """
        index = self.version_dropdown.get_selected()
        if not 0 <= index < len(self.current_versions):
            return
        self.state.payload_pending = intent
        self._load_payload_async(self.current_versions[index].name)

    def _load_payload_async(self, version_name: str) -> None:
        """Start asynchronous background loading of secret payload value."""
        request_id = self.state.start_payload_request()
        self.payload_spinner.start()
        self.copy_val_btn.set_sensitive(False)
        self.text_buffer.set_text(_("Fetching secret..."))
        provider_id = self.active_provider.provider_id
        client = self.active_provider

        self._run_in_background(
            lambda: client.access_secret_payload(version_name),
            lambda loaded: self._on_payload_loaded(
                loaded[0], loaded[1], None, provider_id, request_id
            ),
            lambda exc: self._on_payload_loaded(None, False, str(exc), provider_id, request_id),
        )

    def _on_payload_loaded(
        self,
        payload: Optional[str],
        is_binary: bool,
        error: Optional[str],
        provider_id: str,
        request_id: Optional[int] = None,
    ) -> None:
        """Handle completion of payload query on the GTK main thread.

        Replies that belong to a previous secret, version or request are ignored, so a slow
        response can never show a value under the wrong secret.
        """
        reply = self.state.receive_payload(payload, error, provider_id, request_id)
        if reply.kind == IGNORED:
            return

        self.payload_spinner.stop()
        if reply.kind == FAILED:
            self.text_buffer.set_text(_("Error: {detail}").format(detail=error))
            self.copy_val_btn.set_sensitive(bool(self.current_versions))
            return

        self.copy_val_btn.set_sensitive(True)
        if reply.intent == REVEAL and self.selected_secret:
            self._audit("reveal", self.selected_secret.secret_id)
        if reply.copy:
            self._copy_payload_to_clipboard(reply.copy)
        self._render_payload_text()

    def _render_payload_text(self) -> None:
        """Show the clear value while revealed, otherwise a fixed-length placeholder."""
        # The value only exists in memory while it is revealed
        if self.current_payload is not None and self.is_payload_revealed:
            self.text_buffer.set_text(self.current_payload)
            self.reveal_btn.set_icon_name("view-conceal-symbolic")
            self._arm_reveal_timer()
        else:
            self.text_buffer.set_text(_PAYLOAD_PLACEHOLDER)
            self.reveal_btn.set_icon_name("view-reveal-symbolic")
            self._cancel_reveal_timer()
        self._update_table_view()

    def _update_table_view(self) -> None:
        """Offer the table only while a revealed value is a JSON object, and fill it."""
        keys = (
            parse_key_values(self.current_payload)
            if self.current_payload is not None and self.is_payload_revealed
            else None
        )
        while (row := self.table_list.get_row_at_index(0)) is not None:
            self.table_list.remove(row)
        if keys is None:
            self.table_btn.set_active(False)
            self.table_btn.set_sensitive(False)
            self.value_stack.set_visible_child_name("text")
            return
        self.table_btn.set_sensitive(True)
        for key, value in keys.items():
            row = Adw.ActionRow(
                title=GLib.markup_escape_text(key), subtitle=GLib.markup_escape_text(value)
            )
            row.set_subtitle_lines(3)
            copy_btn = Gtk.Button(
                icon_name="edit-copy-symbolic",
                valign=Gtk.Align.CENTER,
                tooltip_text=_("Copy the value of '%s'") % key,
            )
            copy_btn.add_css_class("flat")
            copy_btn.connect("clicked", lambda _b, k=key, v=value: self._on_copy_key(k, v))
            row.add_suffix(copy_btn)
            self.table_list.append(row)
            label_icon_buttons(row)
        self.value_stack.set_visible_child_name("table" if self.table_btn.get_active() else "text")

    def _on_table_toggled(self, button: Gtk.ToggleButton) -> None:
        """Switch between the raw text and the one-row-per-key table."""
        self.value_stack.set_visible_child_name("table" if button.get_active() else "text")

    def _on_toggle_reveal(self, _btn: Gtk.Button) -> None:
        """Reveal the value (fetching it on demand) or hide it and forget it."""
        if self.is_payload_revealed:
            self.state.hide_payload()
            self._render_payload_text()
        else:
            self._request_payload(REVEAL)
