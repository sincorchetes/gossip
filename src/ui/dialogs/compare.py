"""Dialog that compares two versions of a secret as a unified diff."""

from __future__ import annotations

import threading
from typing import Any, Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk

from src.diffing import ADDED, HEADER, HUNK, REMOVED, DiffLine, diff_payloads
from src.i18n import _
from src.models import SecretVersionItem

_TAG_STYLES = {
    ADDED: "rgba(38, 162, 105, 0.28)",
    REMOVED: "rgba(224, 27, 36, 0.28)",
    HUNK: "rgba(53, 132, 228, 0.22)",
    HEADER: "rgba(128, 128, 128, 0.22)",
}


def _version_label(version: SecretVersionItem) -> str:
    """Build the dropdown/header label for a version."""
    return f"{_('Version %s') % version.version_id} ({version.display_state})"


def _render_diff(buffer: Gtk.TextBuffer, lines: List[DiffLine]) -> None:
    """Write diff lines into the buffer applying a background tag per line kind."""
    buffer.set_text("")
    for line in lines:
        start = buffer.get_end_iter().get_offset()
        buffer.insert(buffer.get_end_iter(), line.text + "\n")
        tag = buffer.get_tag_table().lookup(line.kind)
        if tag is not None:
            buffer.apply_tag(
                tag,
                buffer.get_iter_at_offset(start),
                buffer.get_iter_at_offset(start + len(line.text)),
            )


def _build_diff_view(win: Any) -> Gtk.ScrolledWindow:
    """Create the read-only, tagged text view for the diff and bind its buffer to win."""
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    scrolled.add_css_class("card")
    view = Gtk.TextView()
    view.set_editable(False)
    view.set_cursor_visible(False)
    view.set_monospace(True)
    view.set_wrap_mode(Gtk.WrapMode.CHAR)
    win.diff_buffer = view.get_buffer()
    for kind, color in _TAG_STYLES.items():
        rgba = Gdk.RGBA()
        rgba.parse(color)
        win.diff_buffer.create_tag(kind, background_rgba=rgba)
    scrolled.set_child(view)
    return scrolled


def _show_diff_result(
    win: Any, lines: List[DiffLine], error: Optional[str], identical_message: str
) -> None:
    """Show a comparison result (diff, error or "no differences") on the GTK main thread."""
    win.spinner.stop()
    win.compare_btn.set_sensitive(True)
    if error:
        win.status_label.set_label(_("Error: {detail}").format(detail=error))
        return
    if not lines:
        win.diff_buffer.set_text("")
        win.status_label.set_label(identical_message)
        return
    _render_diff(win.diff_buffer, lines)
    added = sum(1 for line in lines if line.kind == ADDED)
    removed = sum(1 for line in lines if line.kind == REMOVED)
    win.status_label.set_label(_("%d added, %d removed") % (added, removed))


def show_compare_versions_dialog(
    parent_window: Gtk.Window,
    versions: List[SecretVersionItem],
    fetch_payload: Callable[[str], str],
) -> Adw.Window:
    """Open a window that diffs the payloads of two selected secret versions.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        versions: Versions of the secret, newest first.
        fetch_payload: Blocking function returning the plaintext payload of a version name.
            It is called from a worker thread.

    Returns:
        Adw.Window: The presented window (exposes widgets as attributes for testing).
    """
    win = Adw.Window(transient_for=parent_window, modal=True)
    win.set_title(_("Compare versions"))
    win.set_default_size(780, 600)

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    root.append(Adw.HeaderBar())

    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    for setter in (
        body.set_margin_top,
        body.set_margin_bottom,
        body.set_margin_start,
        body.set_margin_end,
    ):
        setter(12)
    root.append(body)

    labels = [_version_label(v) for v in versions]
    controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    controls.append(Gtk.Label(label=_("From")))
    win.from_dropdown = Gtk.DropDown.new_from_strings(labels)
    controls.append(win.from_dropdown)
    controls.append(Gtk.Label(label=_("To")))
    win.to_dropdown = Gtk.DropDown.new_from_strings(labels)
    controls.append(win.to_dropdown)
    win.from_dropdown.set_selected(1 if len(versions) > 1 else 0)
    win.to_dropdown.set_selected(0)

    win.compare_btn = Gtk.Button(label=_("Compare"))
    win.compare_btn.add_css_class("suggested-action")
    controls.append(win.compare_btn)
    win.spinner = Gtk.Spinner()
    controls.append(win.spinner)
    body.append(controls)

    warning = Gtk.Label(label=_("Values are shown in clear text."), xalign=0)
    warning.add_css_class("dim-label")
    body.append(warning)

    win.status_label = Gtk.Label(label="", xalign=0)
    body.append(win.status_label)

    body.append(_build_diff_view(win))

    def on_done(lines: List[DiffLine], error: Optional[str]) -> None:
        """Show the comparison result on the GTK main thread."""
        _show_diff_result(win, lines, error, _("No differences between these versions"))

    def on_compare(_btn: Gtk.Button) -> None:
        """Fetch both payloads in the background and diff them."""
        old_index = win.from_dropdown.get_selected()
        new_index = win.to_dropdown.get_selected()
        if old_index == new_index or not versions:
            win.status_label.set_label(_("Select two different versions"))
            return
        old, new = versions[old_index], versions[new_index]
        win.status_label.set_label(_("Comparing..."))
        win.compare_btn.set_sensitive(False)
        win.spinner.start()

        def worker() -> None:
            """Background worker: fetch both payloads and compute the diff."""
            try:
                lines = diff_payloads(
                    fetch_payload(old.name),
                    fetch_payload(new.name),
                    _version_label(old),
                    _version_label(new),
                )
                GLib.idle_add(on_done, lines, None)
            except Exception as exc:
                GLib.idle_add(on_done, [], str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def on_close(_win: Adw.Window) -> bool:
        """Drop displayed secret values when the window closes."""
        win.diff_buffer.set_text("")
        return False

    win.compare_btn.connect("clicked", on_compare)
    win.connect("close-request", on_close)
    win.set_content(root)
    win.present()
    return win
