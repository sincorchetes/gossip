"""Dialog that compares the current secret with a secret from another context or provider."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.diffing import DiffLine, diff_payloads
from src.i18n import _
from src.models import SecretItem
from src.ui.dialogs.compare import _build_diff_view, _show_diff_result


@dataclass
class CompareTarget:
    """Somewhere a secret can be read from: a provider in one of its contexts.

    Attributes:
        label: Text shown in the selector, e.g. "AWS: prod (eu-west-1)".
        list_secrets: Blocking call returning the secrets there (run in a worker thread).
        fetch_value: Blocking call returning the current value of one of them.
    """

    label: str
    list_secrets: Callable[[], List[SecretItem]]
    fetch_value: Callable[[SecretItem], str]


def show_compare_secrets_dialog(
    parent_window: Gtk.Window,
    current_label: str,
    fetch_current: Callable[[], str],
    targets: List[CompareTarget],
) -> Adw.Window:
    """Open a window that diffs the selected secret against another one.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        current_label: Description of the secret being compared (left side).
        fetch_current: Blocking call returning its value; runs in a worker thread.
        targets: Places the other secret can come from.

    Returns:
        Adw.Window: The presented window (exposes widgets as attributes for testing).
    """
    win = Adw.Window(transient_for=parent_window, modal=True)
    win.set_title(_("Compare with another secret"))
    win.set_default_size(820, 700)
    state: Dict[str, Any] = {"request": 0, "secrets": []}

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

    current = Gtk.Label(label=_("Current: %s") % current_label, xalign=0)
    current.add_css_class("heading")
    body.append(current)

    group = Adw.PreferencesGroup()
    win.target_row = Adw.ComboRow(
        title=_("Compare with"), model=Gtk.StringList.new([t.label for t in targets])
    )
    group.add(win.target_row)
    body.append(group)

    win.search = Gtk.SearchEntry(placeholder_text=_("Filter secrets"))
    body.append(win.search)
    win.secret_list = Gtk.ListBox()
    win.secret_list.add_css_class("boxed-list")
    list_scroll = Gtk.ScrolledWindow()
    list_scroll.set_min_content_height(150)
    list_scroll.set_max_content_height(200)
    list_scroll.set_child(win.secret_list)
    body.append(list_scroll)

    controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    win.compare_btn = Gtk.Button(label=_("Compare"))
    win.compare_btn.add_css_class("suggested-action")
    win.compare_btn.set_sensitive(False)
    controls.append(win.compare_btn)
    win.spinner = Gtk.Spinner()
    controls.append(win.spinner)
    win.status_label = Gtk.Label(label="", xalign=0)
    controls.append(win.status_label)
    body.append(controls)
    warning = Gtk.Label(label=_("Values are shown in clear text."), xalign=0)
    warning.add_css_class("dim-label")
    body.append(warning)

    body.append(_build_diff_view(win))

    def selected_target() -> Optional[CompareTarget]:
        index = win.target_row.get_selected()
        return targets[index] if 0 <= index < len(targets) else None

    def selected_secret() -> Optional[SecretItem]:
        row = win.secret_list.get_selected_row()
        return getattr(row, "secret", None) if row else None

    def fill_list(secrets: List[SecretItem], error: Optional[str], request: int) -> None:
        """Show the secrets of the chosen place unless a newer choice replaced it."""
        if request != state["request"]:
            return
        win.spinner.stop()
        state["secrets"] = secrets
        while (row := win.secret_list.get_row_at_index(0)) is not None:
            win.secret_list.remove(row)
        if error:
            win.status_label.set_label(_("Error: {detail}").format(detail=error))
            return
        win.status_label.set_label(_("%d secrets") % len(secrets))
        for secret in secrets:
            row = Adw.ActionRow(title=GLib.markup_escape_text(secret.secret_id))
            row.secret = secret
            win.secret_list.append(row)
        apply_filter()

    def load_secrets(*_args: object) -> None:
        """List the secrets of the selected place in the background."""
        target = selected_target()
        state["request"] += 1
        request = state["request"]
        win.compare_btn.set_sensitive(False)
        if target is None:
            return
        win.spinner.start()
        win.status_label.set_label(_("Loading..."))

        def worker() -> None:
            try:
                GLib.idle_add(fill_list, target.list_secrets(), None, request)
            except Exception as exc:
                GLib.idle_add(fill_list, [], str(exc), request)

        threading.Thread(target=worker, daemon=True).start()

    def apply_filter(*_args: object) -> None:
        text = win.search.get_text().strip().lower()
        win.secret_list.set_filter_func(
            lambda row: not text or text in getattr(row, "secret").secret_id.lower()
        )

    def on_selection(*_args: object) -> None:
        win.compare_btn.set_sensitive(selected_secret() is not None)

    def on_done(lines: List[DiffLine], error: Optional[str]) -> None:
        """Show the comparison result on the GTK main thread."""
        _show_diff_result(win, lines, error, _("The two values are identical"))

    def on_compare(_btn: Gtk.Button) -> None:
        """Fetch both values in the background and diff them."""
        target, other = selected_target(), selected_secret()
        if target is None or other is None:
            return
        win.status_label.set_label(_("Comparing..."))
        win.compare_btn.set_sensitive(False)
        win.spinner.start()

        def worker() -> None:
            try:
                lines = diff_payloads(
                    fetch_current(),
                    target.fetch_value(other),
                    current_label,
                    f"{target.label} / {other.secret_id}",
                )
                GLib.idle_add(on_done, lines, None)
            except Exception as exc:
                GLib.idle_add(on_done, [], str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def on_close(_win: Adw.Window) -> bool:
        """Drop displayed secret values when the window closes."""
        win.diff_buffer.set_text("")
        return False

    win.target_row.connect("notify::selected", load_secrets)
    win.search.connect("search-changed", apply_filter)
    win.secret_list.connect("row-selected", on_selection)
    win.compare_btn.connect("clicked", on_compare)
    win.connect("close-request", on_close)
    win.set_content(root)
    win.present()
    load_secrets()
    return win
