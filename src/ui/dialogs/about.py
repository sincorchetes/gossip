"""About dialog presentation controller for Gossip application."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import __version__
from src.i18n import _


def show_about_dialog(parent_window: Gtk.Window) -> None:
    """Show the Libadwaita About dialog with version, authors, and license info.

    Args:
        parent_window: GTK parent window to transient the dialog for.
    """
    about = Adw.AboutWindow(
        transient_for=parent_window,
        application_name="Gossip",
        application_icon="dialog-password-symbolic",
        developer_name="Antigravity (Google DeepMind)",
        developers=[
            "Antigravity (Google DeepMind)",
            "sincorchetes.tech",
        ],
        version=__version__,
        comments=_(
            "Multi-Cloud Secret Manager explorer and manager for Google Cloud Platform (GCP), "
            "Amazon Web Services (AWS), Microsoft Azure (Key Vault), and Ansible Vault "
            "with GTK4 and Libadwaita."
        ),
        website="https://sincorchetes.github.io/gossip/",
        issue_url="https://github.com/sincorchetes/gossip/issues",
        copyright="© 2026 Antigravity &amp; sincorchetes.tech",
        license_type=Gtk.License.GPL_2_0,
    )
    about.present()
