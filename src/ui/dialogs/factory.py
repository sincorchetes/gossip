"""One place that opens the application's dialogs, so a window (or a test) can swap them."""

from __future__ import annotations

from src.ui.dialogs.about import show_about_dialog
from src.ui.dialogs.compare import show_compare_versions_dialog
from src.ui.dialogs.compare_secrets import show_compare_secrets_dialog
from src.ui.dialogs.confirm import (
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_confirm_restore_version_dialog,
)
from src.ui.dialogs.metadata import show_edit_metadata_dialog
from src.ui.dialogs.secret import show_add_version_dialog, show_create_secret_dialog
from src.ui.dialogs.transfer import (
    show_export_dialog,
    show_import_dialog,
    show_import_result_dialog,
)


class DialogFactory:
    """The dialogs a window can open, as attributes holding the functions that show them.

    MainWindow owns one instance and its mixins call ``self.dialogs.<name>(...)``. Tests (or a
    different front end) replace an attribute on the instance instead of patching modules.
    """

    def __init__(self) -> None:
        self.about = show_about_dialog
        self.create_secret = show_create_secret_dialog
        self.add_version = show_add_version_dialog
        self.edit_metadata = show_edit_metadata_dialog
        self.confirm_delete = show_confirm_delete_secret_dialog
        self.confirm_destroy = show_confirm_destroy_version_dialog
        self.confirm_restore = show_confirm_restore_version_dialog
        self.compare_versions = show_compare_versions_dialog
        self.compare_secrets = show_compare_secrets_dialog
        self.export = show_export_dialog
        self.import_ = show_import_dialog
        self.import_result = show_import_result_dialog
