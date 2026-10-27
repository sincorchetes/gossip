"""Secret creation and version management modal dialog controllers."""

from __future__ import annotations

from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import _
from src.ui.dialogs.generator import build_generator_button


def show_add_version_dialog(
    parent_window: Gtk.Window,
    secret_id: str,
    on_confirm: Callable[[str], None],
    current_value: Optional[str] = None,
) -> None:
    """Show a modal dialog to enter and submit a new payload version for an existing secret.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        secret_id: Human-readable secret identifier.
        on_confirm: Callback invoked with the new payload text upon submission.
        current_value: Optional existing payload from the previous or active secret version.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("New Version: %s") % secret_id,
        body=_("Enter the new secret payload. A new active version (latest) will be created."),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    box.set_margin_top(12)
    box.set_margin_bottom(12)
    box.set_margin_start(16)
    box.set_margin_end(16)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_height(160)
    scrolled.set_max_content_height(280)
    scrolled.set_min_content_width(380)

    text_view = Gtk.TextView()
    text_view.set_monospace(True)
    text_view.set_wrap_mode(Gtk.WrapMode.CHAR)
    buffer = text_view.get_buffer()
    scrolled.set_child(text_view)

    if current_value is not None:
        copy_check = Gtk.CheckButton(label=_("Copy value from previous version"))
        copy_check.set_margin_bottom(4)

        def on_toggle_copy(btn: Gtk.CheckButton) -> None:
            """Populate or revert the buffer based on copy checkbox state."""
            if btn.get_active():
                buffer.set_text(current_value)
            else:
                start_iter = buffer.get_start_iter()
                end_iter = buffer.get_end_iter()
                if buffer.get_text(start_iter, end_iter, True) == current_value:
                    buffer.set_text("")

        copy_check.connect("toggled", on_toggle_copy)
        box.append(copy_check)

    generator_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    generator_row.set_halign(Gtk.Align.END)
    generator_row.append(Gtk.Label(label=_("Generate a random password")))
    generator_row.append(build_generator_button(buffer))
    box.append(generator_row)
    box.append(scrolled)

    dialog.set_extra_child(box)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("save", _("Save Version"))
    dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("save")
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle user response in add version dialog."""
        if response == "save":
            start_iter = buffer.get_start_iter()
            end_iter = buffer.get_end_iter()
            payload = buffer.get_text(start_iter, end_iter, True)
            if payload:
                on_confirm(payload)

    dialog.connect("response", on_response)
    dialog.present()


def show_create_secret_dialog(
    parent_window: Gtk.Window,
    on_confirm: Callable[[str, str, dict, Optional[str]], None],
    provider: str = "gcp",
) -> None:
    """Show a modal dialog to create a new secret in the active cloud provider.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        on_confirm: Callback invoked with (secret_id, payload, labels_dict, description).
        provider: Provider identifier ('gcp', 'aws', 'azure', 'ansible').
    """
    if provider == "aws":
        heading_text = _("Create New AWS Secret")
        body_text = _(
            "Define the unique identifier, initial payload, and optional tags for AWS Secrets Manager."
        )
    elif provider == "azure":
        heading_text = _("Create New Azure Secret")
        body_text = _(
            "Define the unique identifier, initial payload, and optional tags for Azure Key Vault."
        )
    elif provider == "ssm":
        heading_text = _("Create New AWS Parameter")
        body_text = _(
            "Define the parameter name (e.g. /app/db/password), its value and optional tags. "
            "It is stored as an encrypted SecureString."
        )
    elif provider == "k8s":
        heading_text = _("Create New Kubernetes Secret")
        body_text = _(
            "Define the Secret name and its keys. A JSON object of strings becomes several keys; "
            "any other text is stored under the key 'value'."
        )
    elif provider == "vault":
        heading_text = _("Create New Vault Secret")
        body_text = _(
            "Define the secret path and its value. A JSON object is stored as several keys; "
            "any other text is stored under the key 'value'."
        )
    elif provider == "ansible":
        heading_text = _("Create New Ansible Variable")
        body_text = _(
            "Define the variable name (key) and initial value to store in the Ansible Vault."
        )
    else:
        heading_text = _("Create New GCP Secret")
        body_text = _(
            "Define the unique identifier and initial payload for the new secret in GCP Secret Manager."
        )

    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=heading_text,
        body=body_text,
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_top(12)
    box.set_margin_bottom(12)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.set_size_request(400, -1)

    # Secret ID / Variable Name Entry
    name_label_text = (
        _("Variable name (key):") if provider == "ansible" else _("Secret identifier (ID):")
    )
    name_label = Gtk.Label(label=name_label_text, xalign=0)
    name_label.add_css_class("heading")
    box.append(name_label)

    name_entry = Gtk.Entry()
    name_placeholder = (
        _("e.g. database_password") if provider == "ansible" else _("e.g. my-production-api-key")
    )
    name_entry.set_placeholder_text(name_placeholder)
    box.append(name_entry)

    # Description Entry (helpful in AWS and Azure content_type)
    desc_entry: Optional[Gtk.Entry] = None
    if provider in ("aws", "azure", "ssm"):
        label_text = (
            _("Description (optional):")
            if provider in ("aws", "ssm")
            else _("Content Type / Description (optional):")
        )
        desc_label = Gtk.Label(label=label_text, xalign=0)
        desc_label.add_css_class("dim-label")
        box.append(desc_label)

        desc_entry = Gtk.Entry()
        desc_entry.set_placeholder_text(_("e.g. Credentials for database cluster"))
        box.append(desc_entry)

    # Payload text area
    val_label_text = _("Variable value:") if provider == "ansible" else _("Initial payload:")
    val_label = Gtk.Label(label=val_label_text, xalign=0, hexpand=True)
    val_label.add_css_class("heading")

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_min_content_height(120)
    scrolled.set_max_content_height(200)

    text_view = Gtk.TextView()
    text_view.set_monospace(True)
    text_view.set_wrap_mode(Gtk.WrapMode.CHAR)
    buffer = text_view.get_buffer()
    scrolled.set_child(text_view)

    val_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    val_header.append(val_label)
    val_header.append(build_generator_button(buffer))
    box.append(val_header)
    box.append(scrolled)

    # Optional labels / tags (only for cloud providers)
    labels_entry: Optional[Gtk.Entry] = None
    if provider in ("aws", "azure", "gcp", "ssm"):
        if provider in ("aws", "azure", "ssm"):
            tag_label_text = _("Tags (optional, comma-separated key=value):")
        else:
            tag_label_text = _("Labels (optional, comma-separated):")

        labels_label = Gtk.Label(label=tag_label_text, xalign=0)
        labels_label.add_css_class("dim-label")
        box.append(labels_label)

        labels_entry = Gtk.Entry()
        labels_entry.set_placeholder_text(_("env=prod, service=auth"))
        box.append(labels_entry)

    dialog.set_extra_child(box)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("create", _("Create Secret"))
    dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("create")
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle user response in create secret dialog."""
        if response == "create":
            secret_id = name_entry.get_text().strip()
            if not secret_id:
                return

            start_iter = buffer.get_start_iter()
            end_iter = buffer.get_end_iter()
            payload = buffer.get_text(start_iter, end_iter, True)

            labels_dict = {}
            if labels_entry:
                raw_labels = labels_entry.get_text().strip()
                if raw_labels:
                    for part in raw_labels.split(","):
                        if "=" in part:
                            k, v = part.split("=", 1)
                            if k.strip():
                                labels_dict[k.strip()] = v.strip()

            desc = desc_entry.get_text().strip() if desc_entry else None
            on_confirm(secret_id, payload, labels_dict, desc)

    dialog.connect("response", on_response)
    dialog.present()
