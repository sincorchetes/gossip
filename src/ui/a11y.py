"""Accessibility helpers: give icon-only controls a name that screen readers can announce."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

_NAMEABLE = (Gtk.Button, Gtk.ToggleButton, Gtk.MenuButton)


def label_icon_buttons(widget: Gtk.Widget) -> int:
    """Use the tooltip as the accessible name of every button that has no text of its own.

    Args:
        widget: Root of the widget tree to walk (the window, a list, a row...).

    Returns:
        int: How many buttons received a name.
    """
    named = 0
    if isinstance(widget, _NAMEABLE):
        tooltip = widget.get_tooltip_text()
        if tooltip and not widget.get_label():
            widget.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
            named += 1
    child = widget.get_first_child()
    while child is not None:
        named += label_icon_buttons(child)
        child = child.get_next_sibling()
    return named
