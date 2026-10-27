"""A report users can attach to a bug report, without secrets, names or credentials.

It lists versions, platform, settings that matter for troubleshooting and the last redacted
diagnostic lines. It never includes projects, vaults, servers, secret names or values.
"""

from __future__ import annotations

import os
import platform
import sys
from importlib import metadata
from typing import List, Optional

from src import __version__, audit
from src.age import stale_days
from src.i18n import get_current_language
from src.log import recent_log
from src.readonly import is_locked, is_read_only

PACKAGES = (
    "boto3",
    "botocore",
    "google-cloud-secret-manager",
    "azure-keyvault-secrets",
    "azure-identity",
    "ansible-core",
    "cryptography",
    "PyYAML",
    "PyGObject",
)


def _version(package: str) -> str:
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return "not installed"


def _toolkit_versions() -> str:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, Gtk

        gtk = f"{Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}"
        return f"GTK {gtk}, libadwaita {Adw.get_major_version()}.{Adw.get_minor_version()}"
    except Exception:  # the report must work even when the toolkit cannot be queried
        return "GTK / libadwaita: unknown"


def build_report(active_provider: Optional[str] = None, providers: int = 0) -> str:
    """Assemble the diagnostics text.

    Args:
        active_provider: Identifier of the provider in use (not its project or server).
        providers: Number of providers available.

    Returns:
        str: Plain text ready to copy or save.
    """
    from src.ui.windows.idle import idle_lock_seconds  # imported late: the windows import dialogs

    lines: List[str] = [
        f"Gossip {__version__}",
        f"Python {sys.version.split()[0]} ({platform.python_implementation()})",
        f"System: {platform.system()} {platform.release()} {platform.machine()}",
        _toolkit_versions(),
        f"Language: {get_current_language()}",
        f"Renderer: {os.environ.get('GSK_RENDERER', 'default')}",
        f"Frozen build: {bool(getattr(sys, 'frozen', False))}",
        "",
        "Settings",
        f"  provider: {active_provider or 'unknown'} (of {providers})",
        f"  read-only: {is_read_only()} (locked: {is_locked()})",
        f"  idle lock seconds: {idle_lock_seconds()}",
        f"  stale days: {stale_days()}",
        f"  audit log: {'on' if audit.active_path() else 'off'}",
        "",
        "Packages",
        *(f"  {name}: {_version(name)}" for name in PACKAGES),
        "",
        "Recent log (redacted)",
        *(f"  {line}" for line in (recent_log()[-50:] or ["(empty)"])),
    ]
    return "\n".join(lines) + "\n"
