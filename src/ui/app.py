"""Application entry controller and Libadwaita application lifecycle management."""

from __future__ import annotations

import os
import sys
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    GCPSecretClient,
)
from src.ui.window import MainWindow


CUSTOM_CSS = """
.pill {
    padding-left: 8px;
    padding-right: 8px;
    padding-top: 2px;
    padding-bottom: 2px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: bold;
}

.pill.success {
    background-color: alpha(@success_color, 0.2);
    color: @success_color;
}

.pill.warning {
    background-color: alpha(@warning_color, 0.2);
    color: @warning_color;
}

.pill.error {
    background-color: alpha(@error_color, 0.2);
    color: @error_color;
}

.pill.caption {
    background-color: alpha(@accent_color, 0.15);
    color: @accent_color;
}
"""


class GossipApplication(Adw.Application):
    """Main Libadwaita application controller for Gossip.

    Manages application startup, custom CSS theme styles, provider client
    initialization, and main window presentation.
    """

    def __init__(
        self,
        provider: str = "gcp",
        project_id: Optional[str] = None,
        aws_profile: Optional[str] = None,
        aws_region: Optional[str] = None,
        azure_vault: Optional[str] = None,
        ansible_vault: Optional[str] = None,
        ansible_password_file: Optional[str] = None,
        width: int = 1280,
        height: int = 820,
        maximized: bool = False,
    ):
        """Initialize the GossipApplication.

        Args:
            provider: Initial cloud provider ('gcp', 'aws', 'azure', 'ansible').
            project_id: Optional initial Google Cloud project ID.
            aws_profile: Optional initial AWS credentials profile name.
            aws_region: Optional initial AWS region name.
            azure_vault: Optional initial Azure Key Vault identifier.
            ansible_vault: Optional path to Ansible Vault YAML file.
            ansible_password_file: Optional path to Ansible Vault password file.
            width: Initial window width in pixels.
            height: Initial window height in pixels.
            maximized: If True, presents the window maximized on launch.
        """
        super().__init__(
            application_id="com.github.sincorchetes.gossip_gcp",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.provider = provider
        self.project_id = project_id
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.azure_vault = azure_vault
        self.ansible_vault = ansible_vault
        self.ansible_password_file = ansible_password_file
        self.width = width
        self.height = height
        self.maximized = maximized

        self.gcp_client = GCPSecretClient(project_id=self.project_id)
        self.aws_client = AWSSecretClient(profile_name=self.aws_profile, region_name=self.aws_region)
        self.azure_client = AzureSecretClient(vault_name=self.azure_vault)
        self.ansible_client = AnsibleVaultClient(vault_file=self.ansible_vault, password_file=self.ansible_password_file)
        self.window: Optional[MainWindow] = None

    def do_startup(self):
        """Handle GTK application startup and register custom CSS providers."""
        Adw.Application.do_startup(self)
        self._load_css()
        self._register_icon_theme()

    def _register_icon_theme(self):
        """Register bundled share/icons search paths into GTK IconTheme."""
        display = Gdk.Display.get_default()
        if display:
            theme = Gtk.IconTheme.get_for_display(display)
            if getattr(sys, "frozen", False):
                bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
                for cand in (os.path.join(bundle_dir, "share", "icons"), os.path.join(bundle_dir, "icons")):
                    if os.path.isdir(cand):
                        theme.add_search_path(cand)

    def _load_css(self):
        """Load and apply application-wide custom CSS pill styling."""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CUSTOM_CSS.encode("utf-8"))
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )


    def do_activate(self):
        """Handle GTK application activation, creating and presenting MainWindow."""
        Adw.Application.do_activate(self)
        if not self.window:
            self.window = MainWindow(
                application=self,
                provider=self.provider,
                gcp_client=self.gcp_client,
                aws_client=self.aws_client,
                azure_client=self.azure_client,
                ansible_client=self.ansible_client,
                width=self.width,
                height=self.height,
                maximized=self.maximized,
            )
        self.window.present()


# Alias for backward compatibility
GossipGCPApplication = GossipApplication


def run_app(
    provider: str = "gcp",
    project_id: Optional[str] = None,
    aws_profile: Optional[str] = None,
    aws_region: Optional[str] = None,
    azure_vault: Optional[str] = None,
    ansible_vault: Optional[str] = None,
    ansible_password_file: Optional[str] = None,
    width: int = 1280,
    height: int = 820,
    maximized: bool = False,
) -> int:
    """Launch the Gossip desktop application and enter the GTK event loop.

    Args:
        provider: Initial provider identifier ('gcp', 'aws', 'azure', 'ansible').
        project_id: Optional GCP project ID to query.
        aws_profile: Optional AWS profile name.
        aws_region: Optional AWS region.
        azure_vault: Optional Azure Key Vault name or URI.
        ansible_vault: Optional path to Ansible Vault encrypted file.
        ansible_password_file: Optional path to vault password file.
        width: Initial window width in pixels.
        height: Initial window height in pixels.
        maximized: Whether to start the window maximized.

    Returns:
        int: Application exit code returned from GTK run loop.
    """
    app = GossipApplication(
        provider=provider,
        project_id=project_id,
        aws_profile=aws_profile,
        aws_region=aws_region,
        azure_vault=azure_vault,
        ansible_vault=ansible_vault,
        ansible_password_file=ansible_password_file,
        width=width,
        height=height,
        maximized=maximized,
    )
    return app.run(sys.argv[:1])
