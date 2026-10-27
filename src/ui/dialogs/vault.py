"""HashiCorp Vault / OpenBao connection dialog."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import _
from src.providers.vault import VaultClient


def show_change_vault_dialog(
    parent_window: Gtk.Window,
    client: VaultClient,
    on_success: Callable[[], None],
) -> None:
    """Ask for the server address, KV mount, namespace and token.

    The token is only kept in memory and is dropped when the application locks.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        client: VaultClient provider instance to configure.
        on_success: Callback invoked after the settings were applied.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Vault / OpenBao server"),
        body=_(
            "Plain HTTP is only accepted for localhost. Leave the token empty to use "
            "VAULT_TOKEN or the token from 'vault login'."
        ),
    )

    group = Adw.PreferencesGroup()
    group.set_size_request(440, -1)
    address_row = Adw.EntryRow(title=_("Server address (https://...)"))
    address_row.set_text(client.address or "")
    mount_row = Adw.EntryRow(title=_("KV v2 mount"))
    mount_row.set_text(client.mount)
    namespace_row = Adw.EntryRow(title=_("Namespace (optional)"))
    namespace_row.set_text(client.namespace or "")
    token_row = Adw.PasswordEntryRow(title=_("Token (kept in memory only)"))
    for row in (address_row, mount_row, namespace_row, token_row):
        group.add(row)

    error_label = Gtk.Label(wrap=True, xalign=0)
    error_label.add_css_class("error")
    error_label.set_visible(False)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.append(group)
    box.append(error_label)

    dialog.set_extra_child(box)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("apply", _("Apply"))
    dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("apply")
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Apply the settings, keeping the dialog open when they are rejected."""
        if response != "apply":
            return
        try:
            client.configure(
                address_row.get_text(),
                mount_row.get_text(),
                namespace_row.get_text(),
                token_row.get_text(),
            )
        except ValueError as exc:
            error_label.set_label(str(exc))
            error_label.set_visible(True)
            dialog.present()
            return
        on_success()

    dialog.connect("response", on_response)
    dialog.present()
