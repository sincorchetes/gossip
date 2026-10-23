"""Backward-compatible composite data mixin for MainWindow."""

from __future__ import annotations

from src.ui.window_sidebar import WindowSidebarMixin
from src.ui.window_versions import WindowVersionsMixin


class WindowDataMixin(WindowSidebarMixin, WindowVersionsMixin):
    """Composite mixin combining secret sidebar listing and version history functionality."""

    pass
