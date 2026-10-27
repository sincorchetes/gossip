"""Composite data mixin combining secret sidebar listing and version history."""

from __future__ import annotations

from src.ui.windows.compare import WindowCompareMixin
from src.ui.windows.payload import WindowPayloadMixin
from src.ui.windows.sidebar import WindowSidebarMixin
from src.ui.windows.versions import WindowVersionsMixin


class WindowDataMixin(
    WindowSidebarMixin, WindowVersionsMixin, WindowPayloadMixin, WindowCompareMixin
):
    """Composite mixin combining secret sidebar listing and version history functionality."""

    pass
