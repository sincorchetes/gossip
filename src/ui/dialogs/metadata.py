"""Dialog to edit the labels / tags (and description) of an existing secret."""

from __future__ import annotations

from typing import Callable, Dict, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import _
from src.labels import format_labels, parse_labels


def show_edit_metadata_dialog(
    parent_window: Gtk.Window,
    secret_id: str,
    labels: Dict[str, str],
    description: Optional[str],
    with_description: bool,
    on_confirm: Callable[[Dict[str, str], Optional[str]], None],
) -> Adw.MessageDialog:
    """Let the user change the labels and description of a secret.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        secret_id: Name of the secret, shown in the heading.
        labels: Current labels / tags.
        description: Current description, or None.
        with_description: Whether the provider can edit the description.
        on_confirm: Callback receiving the new labels and description.

    Returns:
        Adw.MessageDialog: The presented dialog (exposes widgets as attributes for testing).
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Edit '%s'") % secret_id,
        body=_("One label per line as key=value. Removing a line removes that label."),
    )
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

    description_row = None
    if with_description:
        group = Adw.PreferencesGroup()
        description_row = Adw.EntryRow(title=_("Description"))
        description_row.set_text(description or "")
        group.add(description_row)
        box.append(group)

    label = Gtk.Label(label=_("Labels / tags"), xalign=0)
    label.add_css_class("heading")
    box.append(label)
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_height(120)
    scrolled.set_min_content_width(380)
    text_view = Gtk.TextView()
    text_view.set_monospace(True)
    text_view.get_buffer().set_text(format_labels(labels))
    scrolled.set_child(text_view)
    box.append(scrolled)

    dialog.set_extra_child(box)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("save", _("Save"))
    dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_close_response("cancel")

    def on_response(_dlg: Adw.MessageDialog, response: str) -> None:
        """Hand the edited values to the caller when the user saves."""
        if response != "save":
            return
        buffer = text_view.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        new_description = description_row.get_text().strip() if description_row else None
        on_confirm(parse_labels(text), new_description)

    dialog.connect("response", on_response)
    dialog.text_view = text_view
    dialog.description_row = description_row
    dialog.present()
    return dialog
