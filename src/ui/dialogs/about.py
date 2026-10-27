"""About dialog presentation controller for Gossip application."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import __version__
from src.diagnostics import build_report
from src.i18n import _
from src.ui.icons import resolve_icon_name

NOTICES_URL = "https://github.com/sincorchetes/gossip/blob/main/THIRD_PARTY_NOTICES.md"

# Components shown in the "Built with" credits: (name, project URL)
CREDITS = (
    ("GTK 4", "https://www.gtk.org"),
    ("libadwaita", "https://gnome.pages.gitlab.gnome.org/libadwaita/"),
    ("PyGObject", "https://pygobject.gnome.org"),
    ("boto3", "https://github.com/boto/boto3"),
    ("Google Cloud Secret Manager client", "https://github.com/googleapis/google-cloud-python"),
    ("Azure SDK for Python", "https://github.com/Azure/azure-sdk-for-python"),
    ("Ansible Core", "https://github.com/ansible/ansible"),
    ("cryptography", "https://github.com/pyca/cryptography"),
    ("PyYAML", "https://pyyaml.org"),
)


def add_third_party_sections(about: Adw.AboutWindow) -> None:
    """Add the third-party credits and license sections to an About window.

    Args:
        about: The About window to extend.
    """
    about.add_link(_("Third-party notices"), NOTICES_URL)
    about.add_credit_section(
        _("AI-assisted development"),
        [
            "Claude (Anthropic) https://www.anthropic.com",
        ],
    )
    about.add_acknowledgement_section(_("Built with"), [f"{name} {url}" for name, url in CREDITS])
    about.add_legal_section(
        "GTK 4, libadwaita, GLib, Pango, GdkPixbuf, librsvg, PyGObject",
        "© The GNOME Project and contributors",
        Gtk.License.LGPL_2_1,
        None,
    )
    about.add_legal_section(
        "Ansible Core and ansible-vault",
        "© Ansible Project and contributors",
        Gtk.License.GPL_3_0,
        None,
    )
    about.add_legal_section(
        _("Python libraries and runtime"),
        None,
        Gtk.License.CUSTOM,
        _(
            "Gossip bundles Python and open-source libraries (boto3, the Google Cloud and "
            "Azure SDKs, cryptography, PyYAML, gRPC and others) under their own licenses, "
            "mostly Apache-2.0, MIT, BSD and MPL-2.0. Their names, versions and complete "
            "license texts are in the THIRD_PARTY_NOTICES file shipped with every package "
            "and at %s"
        )
        % NOTICES_URL,
    )


def show_about_dialog(parent_window: Gtk.Window) -> None:
    """Show the Libadwaita About dialog with version, authors, and license info.

    Args:
        parent_window: GTK parent window to transient the dialog for.
    """
    about = Adw.AboutWindow(
        transient_for=parent_window,
        application_name="Gossip",
        application_icon=resolve_icon_name(
            ["com.github.sincorchetes.gossip_gcp", "dialog-password-symbolic"],
            fallback="dialog-password-symbolic",
        ),
        developer_name="Álvaro Castillo",
        developers=["Álvaro Castillo https://github.com/sincorchetes"],
        version=__version__,
        comments=_(
            "Explorer and manager for secrets in Google Cloud, AWS (Secrets Manager and "
            "Parameter Store), Azure Key Vault, Ansible Vault, HashiCorp Vault / OpenBao and "
            "Kubernetes, with GTK4 and Libadwaita."
        ),
        website="https://sincorchetes.github.io/gossip/",
        issue_url="https://github.com/sincorchetes/gossip/issues",
        copyright="© 2026 Álvaro Castillo",
        license_type=Gtk.License.GPL_3_0,
    )
    add_third_party_sections(about)
    about.set_debug_info(
        build_report(
            getattr(getattr(parent_window, "active_provider", None), "provider_id", None),
            len(getattr(parent_window, "providers", {})),
        )
    )
    about.set_debug_info_filename("gossip-diagnostics.txt")
    about.present()
