"""Azure Key Vault selection dialog controller."""

from __future__ import annotations

import threading
from typing import Callable, List

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.models import AzureVaultItem
from src.providers.azure import AzureSecretClient


def show_change_azure_vault_dialog(
    parent_window: Gtk.Window,
    client: AzureSecretClient,
    on_confirm: Callable[[str], None],
) -> None:
    """Show a dialog allowing user to select or enter an Azure Key Vault name or URL.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        client: AzureSecretClient provider instance.
        on_confirm: Callback invoked with the chosen vault identifier upon confirmation.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Select Azure Key Vault"),
        body=_("Enter the Key Vault name or choose from available vaults in your Azure account."),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.set_margin_top(8)
    box.set_margin_bottom(8)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.set_size_request(440, 360)

    # Text entry for manual input
    entry_group = Adw.PreferencesGroup(title=_("Key Vault Identifier"))
    vault_entry = Gtk.Entry()
    vault_entry.set_placeholder_text(_("e.g. my-keyvault or https://my-keyvault.vault.azure.net/"))
    if client.vault_name:
        vault_entry.set_text(client.vault_name)
    entry_group.add(vault_entry)
    box.append(entry_group)

    # Scrolled list for discovered vaults
    discovered_group = Adw.PreferencesGroup(title=_("Available Key Vaults (Azure CLI)"))
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    scrolled.set_min_content_height(140)
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

    vault_list_box = Gtk.ListBox()
    vault_list_box.set_selection_mode(Gtk.SelectionMode.BROWSE)
    vault_list_box.add_css_class("boxed-list")
    scrolled.set_child(vault_list_box)
    discovered_group.add(scrolled)
    box.append(discovered_group)

    # Populate discovered vaults in background
    def on_row_activated(_lb: Gtk.ListBox, row: Adw.ActionRow | None) -> None:
        """Fill entry and enable apply button on vault row activation."""
        if row and hasattr(row, "vault_name"):
            vault_entry.set_text(row.vault_name)
            dialog.set_response_enabled("select", True)

    vault_list_box.connect("row-activated", on_row_activated)

    def load_vaults_worker() -> None:
        """Background thread discovering available Azure Key Vaults."""
        try:
            vaults = client.list_available_vaults()
            GLib.idle_add(populate_vault_list, vaults)
        except Exception:
            pass

    def populate_vault_list(vaults: List[AzureVaultItem]) -> None:
        """Render discovered Azure Key Vault items into the list box."""
        for v in vaults:
            row = Adw.ActionRow(title=v.name)
            sub = v.location or v.vault_uri
            row.set_subtitle(sub)
            if client.vault_name and v.name.lower() == client.vault_name.lower():
                badge = Gtk.Label(label=_("Active"))
                badge.add_css_class("pill")
                badge.add_css_class("success")
                row.add_suffix(badge)
            row.vault_name = v.name
            vault_list_box.append(row)

    threading.Thread(target=load_vaults_worker, daemon=True).start()

    dialog.set_extra_child(box)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("select", _("Apply"))
    dialog.set_response_appearance("select", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("select")
    dialog.set_close_response("cancel")

    def update_btn_state(*_) -> None:
        """Enable or disable apply button according to entry content."""
        text = vault_entry.get_text().strip()
        dialog.set_response_enabled("select", bool(text))

    vault_entry.connect("changed", update_btn_state)
    update_btn_state()

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle response in Azure vault switcher dialog."""
        if response == "select":
            chosen = vault_entry.get_text().strip()
            if chosen:
                on_confirm(chosen)

    dialog.connect("response", on_response)
    dialog.present()
