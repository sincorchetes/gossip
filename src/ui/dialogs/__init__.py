"""Dialogs package for Gossip UI."""

from src.ui.dialogs.about import show_about_dialog
from src.ui.dialogs.ansible import show_change_ansible_vault_dialog
from src.ui.dialogs.aws import show_change_aws_context_dialog
from src.ui.dialogs.azure import show_change_azure_vault_dialog
from src.ui.dialogs.confirm import (
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
)
from src.ui.dialogs.project import show_change_project_dialog
from src.ui.dialogs.secret import (
    show_add_version_dialog,
    show_create_secret_dialog,
)

__all__ = [
    "show_about_dialog",
    "show_add_version_dialog",
    "show_change_ansible_vault_dialog",
    "show_change_aws_context_dialog",
    "show_change_azure_vault_dialog",
    "show_change_project_dialog",
    "show_confirm_delete_secret_dialog",
    "show_confirm_destroy_version_dialog",
    "show_create_secret_dialog",
]
