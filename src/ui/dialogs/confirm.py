"""Confirmation modal dialog controllers for destructive actions."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import _


def show_confirm_destroy_version_dialog(
    parent_window: Gtk.Window,
    version_id: str,
    on_confirm: Callable[[], None],
) -> None:
    """Show a confirmation dialog before irreversibly destroying a secret version payload.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        version_id: Identifier or number of the version scheduled for destruction.
        on_confirm: Callback invoked if user confirms destruction.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Destroy Version %s?") % version_id,
        body=_(
            "The contents of this version will be purged permanently and irreversibly.\n\n"
            "This action cannot be undone."
        ),
    )
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("destroy", _("Destroy Version"))
    dialog.set_response_appearance("destroy", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle user response in version destruction dialog."""
        if response == "destroy":
            on_confirm()

    dialog.connect("response", on_response)
    dialog.present()


def show_confirm_delete_secret_dialog(
    parent_window: Gtk.Window,
    secret_id: str,
    on_confirm: Callable[[], None],
    provider: str = "gcp",
) -> None:
    """Show a confirmation dialog before permanently deleting a secret.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        secret_id: Identifier of the secret to delete.
        on_confirm: Callback invoked if user confirms deletion.
        provider: Provider identifier ('gcp', 'aws', 'azure', 'ansible').
    """
    if provider == "aws":
        provider_name = "Amazon Web Services (AWS)"
    elif provider == "azure":
        provider_name = "Microsoft Azure (Key Vault)"
    elif provider == "ansible":
        provider_name = "Ansible Vault"
    else:
        provider_name = "Google Cloud Platform (GCP)"

    if provider == "ansible":
        heading = _("Delete Variable '%s'?") % secret_id
        body = _("The variable '%s' will be removed from Ansible Vault.\n\nThis action cannot be undone.") % secret_id
    else:
        heading = _("Delete Secret '%s'?") % secret_id
        body = _(
            "The complete secret and all its versions will be deleted from %s.\n\n"
            "This action cannot be undone."
        ) % provider_name

    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=heading,
        body=body,
    )
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("delete", _("Delete Secret"))
    dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle user response in secret deletion dialog."""
        if response == "delete":
            on_confirm()

    dialog.connect("response", on_response)
    dialog.present()
