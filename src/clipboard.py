"""Clipboard content for secrets, marked so clipboard managers do not keep it in their history.

Several conventions exist and each is honoured by a different tool, so the text is offered
together with all of them. They are best-effort hints: a tool that ignores them still gets the
text, and Gossip additionally wipes the clipboard after a delay.

* ``x-kde-passwordManagerHint`` – KDE Klipper, KeePassXC, many Linux managers.
* ``org.nspasteboard.ConcealedType`` – macOS clipboard managers (nspasteboard.org).
* ``ExcludeClipboardContentFromMonitorProcessing`` and ``CanIncludeInClipboardHistory`` –
  Windows clipboard history and cloud sync.
"""

from __future__ import annotations

import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib

SENSITIVE_FORMATS = {
    "x-kde-passwordManagerHint": b"secret",
    "org.nspasteboard.ConcealedType": b"secret",
    "ExcludeClipboardContentFromMonitorProcessing": b"1",
    "CanIncludeInClipboardHistory": b"\x00\x00\x00\x00",
}


def secret_content(text: str) -> Gdk.ContentProvider:
    """Build clipboard content holding ``text`` plus the "do not record" hints.

    Args:
        text: The secret value to offer as plain text.

    Returns:
        Gdk.ContentProvider: Provider to pass to ``Gdk.Clipboard.set_content``.
    """
    providers = [Gdk.ContentProvider.new_for_value(text)]
    providers.extend(
        Gdk.ContentProvider.new_for_bytes(mime, GLib.Bytes.new(data))
        for mime, data in SENSITIVE_FORMATS.items()
    )
    return Gdk.ContentProvider.new_union(providers)
