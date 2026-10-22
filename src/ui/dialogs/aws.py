"""AWS profile and region context selection dialog controller."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import _
from src.providers.aws import AWSSecretClient


def show_change_aws_context_dialog(
    parent_window: Gtk.Window,
    client: AWSSecretClient,
    on_confirm: Callable[[str, str], None],
) -> None:
    """Show a dialog allowing user to choose AWS profile and AWS region.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        client: AWSSecretClient provider instance.
        on_confirm: Callback invoked with (profile_name, region_name) upon confirmation.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Select AWS Profile & Region"),
        body=_("Choose the AWS credentials profile and target region for Secrets Manager."),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.set_margin_top(8)
    box.set_margin_bottom(8)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.set_size_request(420, -1)

    # Profile group
    prof_group = Adw.PreferencesGroup(title=_("AWS Profile"))
    prof_row = Adw.ActionRow(title=_("Configured Profile"))

    profiles = client.list_available_profiles()
    current_profile = client.profile_name
    if current_profile not in profiles:
        profiles.insert(0, current_profile)

    prof_strings = Gtk.StringList.new(profiles)
    prof_dropdown = Gtk.DropDown.new(prof_strings, None)
    try:
        prof_idx = profiles.index(current_profile)
        prof_dropdown.set_selected(prof_idx)
    except ValueError:
        prof_dropdown.set_selected(0)

    prof_row.add_suffix(prof_dropdown)
    prof_group.add(prof_row)
    box.append(prof_group)

    # Region group
    reg_group = Adw.PreferencesGroup(title=_("AWS Region"))
    reg_row = Adw.ActionRow(title=_("Target Region"))

    regions = client.list_available_regions()
    current_region = client.region_name
    if current_region not in regions:
        regions.insert(0, current_region)

    reg_strings = Gtk.StringList.new(regions)
    reg_dropdown = Gtk.DropDown.new(reg_strings, None)
    try:
        reg_idx = regions.index(current_region)
        reg_dropdown.set_selected(reg_idx)
    except ValueError:
        reg_dropdown.set_selected(0)

    reg_row.add_suffix(reg_dropdown)
    reg_group.add(reg_row)
    box.append(reg_group)

    dialog.set_extra_child(box)

    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("select", _("Apply"))
    dialog.set_response_appearance("select", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("select")
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle user response in AWS context switcher dialog."""
        if response == "select":
            selected_prof_idx = prof_dropdown.get_selected()
            selected_reg_idx = reg_dropdown.get_selected()
            sel_prof = profiles[selected_prof_idx] if 0 <= selected_prof_idx < len(profiles) else "default"
            sel_reg = regions[selected_reg_idx] if 0 <= selected_reg_idx < len(regions) else "us-east-1"
            on_confirm(sel_prof, sel_reg)

    dialog.connect("response", on_response)
    dialog.present()
