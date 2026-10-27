"""Ansible Vault file selection and decrypt dialog controller."""

from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.providers.ansible import AnsibleVaultClient


def show_change_ansible_vault_dialog(
    parent_window: Gtk.Window,
    client: AnsibleVaultClient,
    on_confirm: Callable[[str, Optional[str], Optional[str]], None],
) -> None:
    """Show a dialog allowing user to choose Ansible Vault file, enter password or password file, and unlock.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        client: AnsibleVaultClient provider instance.
        on_confirm: Callback invoked with (vault_file_path, password, password_file_path) upon unlock.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Select Ansible Vault"),
        body=_(
            "Choose your Ansible Vault YAML file and unlock it with your password or password file."
        ),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_margin_top(8)
    box.set_margin_bottom(8)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.set_size_request(460, -1)

    # 1. File group
    file_group = Adw.PreferencesGroup(title=_("Vault File"))
    file_row = Adw.ActionRow(title=_("File Path"))

    file_entry = Gtk.Entry()
    file_entry.set_hexpand(True)
    file_entry.set_placeholder_text(_("e.g. vault.yml or group_vars/all/vault.yml"))
    if client.vault_file:
        file_entry.set_text(client.vault_file)
    else:
        file_entry.set_text("vault.yml")
    file_row.add_suffix(file_entry)

    browse_file_btn = Gtk.Button(icon_name="document-open-symbolic")
    browse_file_btn.set_tooltip_text(_("Browse vault file..."))

    def on_browse_file(_btn: Gtk.Button) -> None:
        """Open system file chooser to locate an Ansible Vault file."""
        file_dialog = Gtk.FileDialog(title=_("Select Ansible Vault File"))

        def on_open_finish(dlg: Gtk.FileDialog, res: Any) -> None:
            """Handle file chooser result for vault file selection."""
            try:
                gfile = dlg.open_finish(res)
                if gfile and gfile.get_path():
                    file_entry.set_text(gfile.get_path())
            except Exception:
                pass

        file_dialog.open(parent_window, None, on_open_finish)

    browse_file_btn.connect("clicked", on_browse_file)
    file_row.add_suffix(browse_file_btn)
    file_group.add(file_row)

    # Local detected files (if any)
    local_files = client.find_local_vault_files()
    if local_files:
        disc_row = Adw.ActionRow(title=_("Detected in Project"))
        disc_strings = [_("Choose a detected file...")] + [os.path.relpath(p) for p in local_files]
        disc_dropdown = Gtk.DropDown.new_from_strings(disc_strings)

        def on_disc_selected(_dd: Gtk.DropDown, _param: Any) -> None:
            """Handle selection from discovered local vault files dropdown."""
            idx = disc_dropdown.get_selected()
            if idx > 0 and idx - 1 < len(local_files):
                file_entry.set_text(local_files[idx - 1])

        disc_dropdown.connect("notify::selected", on_disc_selected)
        disc_row.add_suffix(disc_dropdown)
        file_group.add(disc_row)

    box.append(file_group)

    # 2. Authentication group
    auth_group = Adw.PreferencesGroup(title=_("Vault Authentication"))

    # Password entry
    pwd_row = Adw.PasswordEntryRow(title=_("Vault Password"))
    if client.password:
        pwd_row.set_text(client.password)
    auth_group.add(pwd_row)

    # Password file entry
    pass_file_row = Adw.ActionRow(title=_("Or Password File (.vault_pass)"))
    pass_file_entry = Gtk.Entry()
    pass_file_entry.set_hexpand(True)
    pass_file_entry.set_placeholder_text(_("~/.vault_pass"))
    if client.password_file:
        pass_file_entry.set_text(client.password_file)
    pass_file_row.add_suffix(pass_file_entry)

    browse_pass_btn = Gtk.Button(icon_name="document-open-symbolic")
    browse_pass_btn.set_tooltip_text(_("Browse password file..."))

    def on_browse_pass(_btn: Gtk.Button) -> None:
        """Open system file chooser to locate a vault password file."""
        pass_dialog = Gtk.FileDialog(title=_("Select Password File"))

        def on_pass_finish(dlg: Gtk.FileDialog, res: Any) -> None:
            """Handle file chooser result for vault password file."""
            try:
                gfile = dlg.open_finish(res)
                if gfile and gfile.get_path():
                    pass_file_entry.set_text(gfile.get_path())
            except Exception:
                pass

        pass_dialog.open(parent_window, None, on_pass_finish)

    browse_pass_btn.connect("clicked", on_browse_pass)
    pass_file_row.add_suffix(browse_pass_btn)
    auth_group.add(pass_file_row)

    box.append(auth_group)

    # Error message label
    error_lbl = Gtk.Label(label="", wrap=True, xalign=0)
    error_lbl.add_css_class("error")
    error_lbl.set_visible(False)
    box.append(error_lbl)

    dialog.set_extra_child(box)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("unlock", _("Unlock Vault"))
    dialog.set_response_appearance("unlock", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("unlock")
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle user action in Ansible Vault configuration dialog."""
        if response == "unlock":
            vf = file_entry.get_text().strip()
            pwd = pwd_row.get_text()
            pfile = pass_file_entry.get_text().strip() or None
            if not vf:
                error_lbl.set_label(_("Please enter a valid vault file path."))
                error_lbl.set_visible(True)
                return

            dialog.set_response_enabled("unlock", False)
            error_lbl.set_visible(False)

            def unlock_worker() -> None:
                """Background thread attempting to decrypt and validate Ansible Vault."""
                try:
                    client.unlock(vault_file=vf, password=pwd or None, password_file=pfile)
                    GLib.idle_add(on_unlock_success, vf, pwd or None, pfile)
                except Exception as exc:
                    GLib.idle_add(on_unlock_failed, str(exc))

            def on_unlock_success(
                vf_val: str, pwd_val: Optional[str], pfile_val: Optional[str]
            ) -> None:
                """Callback on GTK main thread when vault is unlocked successfully."""
                dialog.close()
                on_confirm(vf_val, pwd_val, pfile_val)

            def on_unlock_failed(err_msg: str) -> None:
                """Callback on GTK main thread displaying decryption failure."""
                error_lbl.set_label(err_msg)
                error_lbl.set_visible(True)
                dialog.set_response_enabled("unlock", True)

            threading.Thread(target=unlock_worker, daemon=True).start()

    dialog.connect("response", on_response)
    dialog.present()
