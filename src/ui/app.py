"""Application entry controller and Libadwaita application lifecycle management."""

from __future__ import annotations

import os
import sys
from typing import Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from src import (
    providers as _providers,  # noqa: F401  (imports every client: PyInstaller bundles them)
)
from src import registry, state
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
        width: int = 1280,
        height: int = 820,
        maximized: bool = False,
        **options: Optional[str],
    ):
        """Initialize the GossipApplication.

        Args:
            provider: Initial provider identifier (see ``registry.PROVIDER_IDS``).
            width: Initial window width in pixels.
            height: Initial window height in pixels.
            maximized: If True, presents the window maximized on launch.
            **options: Provider settings by name (``project_id``, ``aws_profile``,
                ``vault_addr``, ...; see ``registry.option_names()``). Missing ones mean
                "not given" and fall back to the saved context or autodetection.

        Raises:
            TypeError: If an option name is not one the registry knows.
        """
        unknown = set(options) - set(registry.option_names())
        if unknown:
            raise TypeError(f"unknown provider option(s): {', '.join(sorted(unknown))}")
        super().__init__(
            application_id="com.github.sincorchetes.gossip_gcp",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.provider = provider
        self.options = dict(options)
        self.width = width
        self.height = height
        self.maximized = maximized

        self.clients = registry.create_clients(self.options)
        for provider_id, client in self.clients.items():
            setattr(self, f"{provider_id}_client", client)  # gcp_client, aws_client, ...
        self._restore_saved_contexts()
        self.window: Optional[MainWindow] = None

    def _restore_saved_contexts(self) -> None:
        """Re-apply the last project, vault, server... for providers not set on the command line."""
        saved = state.load()["contexts"]
        for spec in registry.PROVIDERS:
            if not spec.is_explicit(self.options) and saved.get(spec.id):
                self.clients[spec.id].restore_context(saved[spec.id])

    def do_startup(self):
        """Handle GTK application startup and register custom CSS providers."""
        Adw.Application.do_startup(self)
        if sys.platform == "darwin":
            from src.dock_icon import set_dock_icon

            set_dock_icon()
        self._load_css()
        self._register_icon_theme()
        self._apply_saved_theme()

    def _apply_saved_theme(self) -> None:
        """Restore the light or dark scheme chosen in a previous session."""
        theme = state.load()["ui"].get("theme")
        if theme in ("light", "dark"):
            Adw.StyleManager.get_default().set_color_scheme(
                Adw.ColorScheme.FORCE_LIGHT if theme == "light" else Adw.ColorScheme.FORCE_DARK
            )

    def _register_icon_theme(self):
        """Register bundled share/icons search paths into GTK IconTheme."""
        display = Gdk.Display.get_default()
        if display:
            theme = Gtk.IconTheme.get_for_display(display)
            Gtk.Window.set_default_icon_name(self.get_application_id() or "")
            if getattr(sys, "frozen", False):
                bundle_dir = getattr(
                    sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable))
                )
                for cand in (
                    os.path.join(bundle_dir, "share", "icons"),
                    os.path.join(bundle_dir, "icons"),
                ):
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
                providers=self.clients,
                width=self.width,
                height=self.height,
                maximized=self.maximized,
            )
        self.window.present()


# Alias for backward compatibility
GossipGCPApplication = GossipApplication


def run_app(
    provider: str = "gcp",
    width: int = 1280,
    height: int = 820,
    maximized: bool = False,
    **options: Optional[str],
) -> int:
    """Launch the Gossip desktop application and enter the GTK event loop.

    Args:
        provider: Initial provider identifier.
        width: Initial window width in pixels.
        height: Initial window height in pixels.
        maximized: Whether to start the window maximized.
        **options: Provider settings by name, as for GossipApplication.

    Returns:
        int: Application exit code returned from GTK run loop.
    """
    app = GossipApplication(
        provider=provider, width=width, height=height, maximized=maximized, **options
    )
    return app.run(sys.argv[:1])
