"""Dialogs package for Gossip UI."""

from src.ui.dialogs.about import show_about_dialog
from src.ui.dialogs.ansible import show_change_ansible_vault_dialog
from src.ui.dialogs.aws import show_change_aws_context_dialog
from src.ui.dialogs.azure import show_change_azure_vault_dialog
from src.ui.dialogs.compare import show_compare_versions_dialog
from src.ui.dialogs.compare_secrets import CompareTarget, show_compare_secrets_dialog
from src.ui.dialogs.confirm import (
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_confirm_restore_version_dialog,
)
from src.ui.dialogs.kubernetes import show_change_kubernetes_dialog
from src.ui.dialogs.metadata import show_edit_metadata_dialog
from src.ui.dialogs.project import show_change_project_dialog
from src.ui.dialogs.secret import (
    show_add_version_dialog,
    show_create_secret_dialog,
)
from src.ui.dialogs.transfer import (
    show_export_dialog,
    show_import_dialog,
    show_import_result_dialog,
)
from src.ui.dialogs.vault import show_change_vault_dialog

__all__ = [
    "show_about_dialog",
    "show_add_version_dialog",
    "show_change_ansible_vault_dialog",
    "show_change_aws_context_dialog",
    "show_change_azure_vault_dialog",
    "show_change_kubernetes_dialog",
    "show_change_project_dialog",
    "show_change_vault_dialog",
    "CompareTarget",
    "show_compare_secrets_dialog",
    "show_compare_versions_dialog",
    "show_confirm_delete_secret_dialog",
    "show_confirm_destroy_version_dialog",
    "show_confirm_restore_version_dialog",
    "show_create_secret_dialog",
    "show_edit_metadata_dialog",
    "show_export_dialog",
    "show_import_dialog",
    "show_import_result_dialog",
]
