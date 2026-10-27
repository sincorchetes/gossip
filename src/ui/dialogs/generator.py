"""Popover button that fills a text buffer with a freshly generated password."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from src.i18n import _
from src.passwords import DEFAULT_LENGTH, MAX_LENGTH, MIN_LENGTH, generate_password
from src.ui.icons import resolve_icon_name


def build_generator_button(buffer: Gtk.TextBuffer) -> Gtk.MenuButton:
    """Create a "Generate password" button whose popover writes into ``buffer``.

    Args:
        buffer: Text buffer that receives the generated password (replacing its content).

    Returns:
        Gtk.MenuButton: The button; options are exposed as attributes for testing.
    """
    popover = Gtk.Popover()
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    for side in ("top", "bottom", "start", "end"):
        getattr(box, f"set_margin_{side}")(12)

    length = Gtk.SpinButton.new_with_range(MIN_LENGTH, MAX_LENGTH, 1)
    length.set_value(DEFAULT_LENGTH)
    length_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    length_row.append(Gtk.Label(label=_("Length"), hexpand=True, xalign=0))
    length_row.append(length)
    box.append(length_row)

    checks = {}
    for key, label, active in (
        ("lower", _("Lowercase letters"), True),
        ("upper", _("Uppercase letters"), True),
        ("digits", _("Digits"), True),
        ("symbols", _("Symbols"), True),
        ("avoid_ambiguous", _("Avoid look-alike characters (0 O 1 l I)"), False),
    ):
        check = Gtk.CheckButton(label=label)
        check.set_active(active)
        checks[key] = check
        box.append(check)

    generate = Gtk.Button(label=_("Generate"))
    generate.add_css_class("suggested-action")
    box.append(generate)

    def on_generate(_btn: Gtk.Button) -> None:
        """Replace the buffer's text with a new password using the chosen options."""
        options = {key: check.get_active() for key, check in checks.items()}
        if not any(options[k] for k in ("lower", "upper", "digits", "symbols")):
            return
        buffer.set_text(generate_password(length=length.get_value_as_int(), **options))
        popover.popdown()

    generate.connect("clicked", on_generate)
    popover.set_child(box)

    button = Gtk.MenuButton(
        icon_name=resolve_icon_name(
            ["dialog-password-symbolic", "view-refresh-symbolic"],
            fallback="view-refresh-symbolic",
        ),
        tooltip_text=_("Generate a random password"),
    )
    button.set_popover(popover)
    button.length = length
    button.checks = checks
    button.generate = generate
    return button
