"""Backward-compatible facade for MainWindow and window components."""

from __future__ import annotations

from src.ui.dialogs import (
    show_about_dialog,
    show_add_version_dialog,
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_confirm_restore_version_dialog,
    show_create_secret_dialog,
    show_edit_metadata_dialog,
)
from src.ui.icons import resolve_icon_name
from src.ui.windows import (
    MainWindow,
    WindowActionsMixin,
    WindowBuilderMixin,
    WindowDataMixin,
    WindowDetailMixin,
    WindowNavMixin,
    WindowSidebarMixin,
    WindowVersionsMixin,
)

__all__ = [
    "MainWindow",
    "WindowActionsMixin",
    "WindowBuilderMixin",
    "WindowDataMixin",
    "WindowDetailMixin",
    "WindowNavMixin",
    "WindowSidebarMixin",
    "WindowVersionsMixin",
    "resolve_icon_name",
    "show_about_dialog",
    "show_add_version_dialog",
    "show_confirm_delete_secret_dialog",
    "show_confirm_destroy_version_dialog",
    "show_confirm_restore_version_dialog",
    "show_create_secret_dialog",
    "show_edit_metadata_dialog",
]
