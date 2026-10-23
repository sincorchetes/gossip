"""Window components and main application window package."""

from __future__ import annotations

from src.ui.dialogs import (
    show_about_dialog,
    show_add_version_dialog,
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_create_secret_dialog,
)
from src.ui.icons import resolve_icon_name
from src.ui.windows.actions import WindowActionsMixin
from src.ui.windows.builder import WindowBuilderMixin
from src.ui.windows.data import WindowDataMixin
from src.ui.windows.detail import WindowDetailMixin
from src.ui.windows.main import MainWindow
from src.ui.windows.nav import WindowNavMixin
from src.ui.windows.sidebar import WindowSidebarMixin
from src.ui.windows.versions import WindowVersionsMixin

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
    "show_create_secret_dialog",
]
