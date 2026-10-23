"""Icon resolution utilities for GTK4 themes."""

from __future__ import annotations

from typing import Sequence

from gi.repository import Gdk, Gtk


def resolve_icon_name(candidates: Sequence[str], fallback: str = "image-missing") -> str:
    """Return the first icon name from candidates available in the current GTK theme.

    Args:
        candidates: Sequence of icon name strings to check in priority order.
        fallback: Fallback icon name if none of the candidates are available.

    Returns:
        str: First available icon name, or fallback if none exist.
    """
    display = Gdk.Display.get_default()
    if display:
        theme = Gtk.IconTheme.get_for_display(display)
        for name in candidates:
            if theme.has_icon(name):
                return name
    return candidates[0] if candidates else fallback
