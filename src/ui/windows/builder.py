"""UI widget layout construction and dynamic localization update mixin for MainWindow."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import _, get_current_language
from src.ui.dialogs import show_about_dialog
from src.ui.icons import resolve_icon_name

if TYPE_CHECKING:
    from src.models import SecretItem
    from src.providers import BaseSecretProvider


class WindowBuilderMixin:
    """Constructs widgets, layouts, and handles dynamic localization text reloads."""

    # UI widget attributes
    toast_overlay: Adw.ToastOverlay
    window_title: Adw.WindowTitle
    provider_dropdown: Gtk.DropDown
    context_btn: Gtk.Button
    refresh_btn: Gtk.Button
    lang_btn: Gtk.Button
    theme_btn: Gtk.Button
    about_btn: Gtk.Button
    banner: Adw.Banner
    detail_stack: Gtk.Stack
    placeholder_page: Adw.StatusPage
    detail_scroll: Gtk.ScrolledWindow
    detail_container: Gtk.Box

    providers: dict[str, BaseSecretProvider]
    active_provider: BaseSecretProvider
    secrets: list[SecretItem]
    selected_secret: SecretItem | None

    def _build_ui(self) -> None:
        """Construct the complete GTK4 and Libadwaita user interface layout."""
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)  # type: ignore[attr-defined]

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.toast_overlay.set_child(main_box)

        # 1. HeaderBar
        header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(
            title=_("Gossip"),
            subtitle=self._get_context_subtitle(),  # type: ignore[attr-defined]
        )
        header.set_title_widget(self.window_title)

        # Provider switcher (GCP / AWS / Azure / Ansible)
        provider_keys = list(self.providers.keys())
        provider_display_names = [self.providers[k].display_name for k in provider_keys]
        self.provider_dropdown = Gtk.DropDown.new_from_strings(provider_display_names)
        initial_idx = provider_keys.index(self.active_provider.provider_id)
        self.provider_dropdown.set_selected(initial_idx)
        self.provider_dropdown.connect("notify::selected", self._on_provider_changed)  # type: ignore[attr-defined]
        header.pack_start(self.provider_dropdown)

        # Context switch button (Project for GCP, Profile/Region for AWS, Vault for Azure/Ansible)
        self.context_btn = Gtk.Button(
            icon_name=self._get_context_btn_icon(),  # type: ignore[attr-defined]
            tooltip_text=self._get_context_btn_tooltip(),  # type: ignore[attr-defined]
        )
        self.context_btn.connect("clicked", self._on_change_context_clicked)  # type: ignore[attr-defined]
        header.pack_start(self.context_btn)

        self.refresh_btn = Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text=_("Reload secrets"),
        )
        self.refresh_btn.connect("clicked", lambda _: self._load_secrets_async())  # type: ignore[attr-defined]
        header.pack_start(self.refresh_btn)

        # End buttons: Language toggle (ES/EN), Theme toggle, About
        self.lang_btn = Gtk.Button(
            label=get_current_language().upper(),
            tooltip_text=_("Switch language (ES / EN)"),
        )
        self.lang_btn.add_css_class("flat")
        self.lang_btn.connect("clicked", self._toggle_language)  # type: ignore[attr-defined]
        header.pack_end(self.lang_btn)

        self.theme_btn = Gtk.Button(
            icon_name=resolve_icon_name(
                ["weather-clear-night-symbolic", "display-brightness-symbolic"],
                fallback="display-brightness-symbolic",
            ),
            tooltip_text=_("Toggle light/dark theme"),
        )
        self.theme_btn.connect("clicked", self._toggle_theme)  # type: ignore[attr-defined]
        header.pack_end(self.theme_btn)

        self.about_btn = Gtk.Button(
            icon_name=resolve_icon_name(
                ["help-about-symbolic", "dialog-information-symbolic", "info-outline-symbolic"],
                fallback="dialog-information-symbolic",
            ),
            tooltip_text=_("About Gossip"),
        )

        def _open_about(_: Gtk.Button) -> None:
            win_mod = sys.modules.get("src.ui.window") or sys.modules.get("src.ui.windows")
            dlg = getattr(win_mod, "show_about_dialog", show_about_dialog)
            dlg(self)

        self.about_btn.connect("clicked", _open_about)
        header.pack_end(self.about_btn)

        main_box.append(header)

        # Banner for warnings / auth errors
        self.banner = Adw.Banner()
        self.banner.set_revealed(False)
        main_box.append(self.banner)

        # 2. Main Paned Layout (Sidebar + Detail)
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_position(360)
        paned.set_wide_handle(True)
        paned.set_vexpand(True)
        paned.set_hexpand(True)
        main_box.append(paned)

        # Left: Sidebar
        paned.set_start_child(self._build_sidebar_widgets())  # type: ignore[attr-defined]

        # Right: Detail Area
        self.detail_stack = Gtk.Stack()
        self.detail_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        paned.set_end_child(self.detail_stack)

        # Detail: Placeholder when no secret is selected
        self.placeholder_page = Adw.StatusPage(
            title=_("No secret selected"),
            description=_(
                "Select a secret from the sidebar to inspect its configuration, versions, and payload."
            ),
            icon_name="dialog-password-symbolic",
        )
        self.detail_stack.add_named(self.placeholder_page, "placeholder")

        # Detail: Content View
        self.detail_scroll = Gtk.ScrolledWindow()
        self.detail_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.detail_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.detail_container.set_margin_top(20)
        self.detail_container.set_margin_bottom(24)
        self.detail_container.set_margin_start(24)
        self.detail_container.set_margin_end(24)
        self.detail_scroll.set_child(self.detail_container)
        self.detail_stack.add_named(self.detail_scroll, "content")

        self._build_detail_widgets()  # type: ignore[attr-defined]
        self.detail_stack.set_visible_child_name("placeholder")

    def _update_ui_texts(self) -> None:
        """Dynamically reloads all visible UI strings according to the active language."""
        self.set_title(_("Gossip"))  # type: ignore[attr-defined]
        self.window_title.set_title(_("Gossip"))
        self._update_header_and_tooltips()  # type: ignore[attr-defined]
        if self.banner.get_revealed():
            self.banner.set_title(self._get_error_text())  # type: ignore[attr-defined]

        self.refresh_btn.set_tooltip_text(_("Reload secrets"))
        self.theme_btn.set_tooltip_text(_("Toggle light/dark theme"))
        self.about_btn.set_tooltip_text(_("About Gossip"))
        self.lang_btn.set_tooltip_text(_("Switch language (ES / EN)"))

        self._update_sidebar_texts()  # type: ignore[attr-defined]
        self._update_detail_texts()  # type: ignore[attr-defined]

        if self.secrets:
            self._render_secret_list()  # type: ignore[attr-defined]
        if self.selected_secret:
            self._update_detail_labels()  # type: ignore[attr-defined]
