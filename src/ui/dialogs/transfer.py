"""Dialogs for exporting and importing secrets."""

from __future__ import annotations

from typing import Callable, List, Set

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.transfer import NEW_VERSION, SKIP_EXISTING, ImportResult, TransferEntry

_MAX_LISTED_FAILURES = 5
_MAX_PREVIEW_ROWS = 200


def show_export_dialog(
    parent_window: Gtk.Window,
    provider_name: str,
    count: int,
    on_confirm: Callable[[bool], None],
) -> Adw.MessageDialog:
    """Ask how to export the current secrets.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        provider_name: Display name of the active provider.
        count: Number of secrets that will be exported.
        on_confirm: Callback receiving True when secret values must be included.

    Returns:
        Adw.MessageDialog: The presented dialog.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Export secrets"),
        body=_(
            "Export %d secrets from %s to a JSON file. "
            "Values are not included unless you tick the box below."
        )
        % (count, provider_name),
    )
    include_check = Gtk.CheckButton(
        label=_("Include secret values (the file will contain them in clear text)")
    )
    dialog.set_extra_child(include_check)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("export", _("Export"))
    dialog.set_response_appearance("export", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_close_response("cancel")

    def on_response(_dlg: Adw.MessageDialog, response: str) -> None:
        """Forward the confirmation together with the chosen option."""
        if response == "export":
            on_confirm(include_check.get_active())

    dialog.connect("response", on_response)
    dialog.present()
    return dialog


def show_import_dialog(
    parent_window: Gtk.Window,
    provider_name: str,
    entries: List[TransferEntry],
    existing_ids: Set[str],
    on_confirm: Callable[[str], None],
) -> Adw.MessageDialog:
    """Preview an import and ask how to treat secrets that already exist.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        provider_name: Display name of the active provider.
        entries: Entries read from the import file.
        existing_ids: Ids already present in the active provider.
        on_confirm: Callback receiving SKIP_EXISTING or NEW_VERSION when the user confirms.

    Returns:
        Adw.MessageDialog: The presented dialog (exposes the strategy row for testing).
    """
    existing = [entry for entry in entries if entry.secret_id in existing_ids]
    fresh = len(entries) - len(existing)
    with_value = sum(1 for entry in entries if entry.value is not None)
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Import secrets"),
        body=_("Import into %s: %d new, %d already exist. %d of the entries include a value.")
        % (provider_name, fresh, len(existing), with_value),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    listing = Gtk.ListBox()
    listing.set_selection_mode(Gtk.SelectionMode.NONE)
    listing.add_css_class("boxed-list")
    for entry in entries[:_MAX_PREVIEW_ROWS]:
        row = Adw.ActionRow(title=GLib.markup_escape_text(entry.secret_id))
        exists = entry.secret_id in existing_ids
        row.set_subtitle(
            (_("Already exists") if exists else _("New"))
            + ("" if entry.value is not None else " · " + _("no value"))
        )
        listing.append(row)
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_height(160)
    scrolled.set_max_content_height(260)
    scrolled.set_min_content_width(380)
    scrolled.set_child(listing)
    box.append(scrolled)
    if len(entries) > _MAX_PREVIEW_ROWS:
        box.append(Gtk.Label(label=_("… and %d more") % (len(entries) - _MAX_PREVIEW_ROWS)))

    strategy_row = Adw.ComboRow(
        title=_("When a secret already exists"),
        model=Gtk.StringList.new(
            [_("Skip it (keep the current value)"), _("Add the imported value as a new version")]
        ),
    )
    strategy_row.set_sensitive(bool(existing))
    group = Adw.PreferencesGroup()
    group.add(strategy_row)
    box.append(group)
    dialog.set_extra_child(box)
    dialog.strategy_row = strategy_row

    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("import", _("Import"))
    dialog.set_response_appearance("import", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_close_response("cancel")

    def on_response(_dlg: Adw.MessageDialog, response: str) -> None:
        """Run the import when confirmed, with the chosen treatment of existing secrets."""
        if response == "import":
            on_confirm(NEW_VERSION if strategy_row.get_selected() == 1 else SKIP_EXISTING)

    dialog.connect("response", on_response)
    dialog.present()
    return dialog


def show_import_result_dialog(parent_window: Gtk.Window, result: ImportResult) -> Adw.MessageDialog:
    """Summarise what an import created, skipped and could not create.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        result: Outcome of the import.

    Returns:
        Adw.MessageDialog: The presented dialog.
    """
    body = _("Created: %d\nNew version added: %d\nSkipped (already exist): %d\nFailed: %d") % (
        len(result.created),
        len(result.updated),
        len(result.skipped),
        len(result.failed),
    )
    if result.failed:
        shown = [f"• {name}: {error}" for name, error in result.failed[:_MAX_LISTED_FAILURES]]
        body += "\n\n" + "\n".join(shown)
        hidden = len(result.failed) - _MAX_LISTED_FAILURES
        if hidden > 0:
            body += "\n" + _("… and %d more") % hidden
    dialog = Adw.MessageDialog(transient_for=parent_window, heading=_("Import finished"), body=body)
    dialog.add_response("close", _("Close"))
    dialog.set_close_response("close")
    dialog.present()
    return dialog
