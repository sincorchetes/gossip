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
    on_confirm: Callable[..., None],
    provider: str = "gcp",
) -> None:
    """Show a confirmation dialog before permanently deleting a secret.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        secret_id: Identifier of the secret to delete.
        on_confirm: Callback invoked if the user confirms; for AWS Secrets Manager it receives
            ``immediate=True`` when the user asked to skip the recovery window.

        provider: Provider identifier ('gcp', 'aws', 'azure', 'ansible').
    """
    if provider == "aws":
        provider_name = "Amazon Web Services (AWS)"
    elif provider == "azure":
        provider_name = "Microsoft Azure (Key Vault)"
    elif provider == "ansible":
        provider_name = "Ansible Vault"
    elif provider == "ssm":
        provider_name = "AWS Systems Manager (Parameter Store)"
    elif provider == "k8s":
        provider_name = "Kubernetes"
    elif provider == "vault":
        provider_name = "HashiCorp Vault / OpenBao"
    else:
        provider_name = "Google Cloud Platform (GCP)"

    if provider == "ansible":
        heading = _("Delete Variable '%s'?") % secret_id
        body = (
            _(
                "The variable '%s' will be removed from Ansible Vault.\n\nThis action cannot be undone."
            )
            % secret_id
        )
    elif provider == "aws":
        heading = _("Delete Secret '%s'?") % secret_id
        body = _(
            "The secret will be scheduled for deletion from AWS Secrets Manager and can be "
            "restored during the next 7 days."
        )
    else:
        heading = _("Delete Secret '%s'?") % secret_id
        body = (
            _(
                "The complete secret and all its versions will be deleted from %s.\n\n"
                "This action cannot be undone."
            )
            % provider_name
        )

    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=heading,
        body=body,
    )
    immediate_check = None
    if provider == "aws":
        immediate_check = Gtk.CheckButton(label=_("Delete immediately, without a recovery window"))
        dialog.set_extra_child(immediate_check)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("delete", _("Delete Secret"))
    dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle user response in secret deletion dialog."""
        if response != "delete":
            return
        if immediate_check is not None:
            on_confirm(immediate=immediate_check.get_active())
        else:
            on_confirm()

    dialog.connect("response", on_response)
    dialog.present()


def show_confirm_restore_version_dialog(
    parent_window: Gtk.Window,
    version_id: str,
    on_confirm: Callable[[], None],
) -> None:
    """Ask before writing an older version's value as the new current version.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        version_id: Identifier or number of the version to restore.
        on_confirm: Callback invoked if the user confirms.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Restore Version %s?") % version_id,
        body=_(
            "Its value will be saved as a new version and become the current one. "
            "The versions you already have are kept."
        ),
    )
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("restore", _("Restore"))
    dialog.set_response_appearance("restore", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle the user's answer."""
        if response == "restore":
            on_confirm()

    dialog.connect("response", on_response)
    dialog.present()
