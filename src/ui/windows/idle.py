"""Inactivity lock mixin: hides and forgets revealed secrets after a period without input."""

from __future__ import annotations

import math
import os
import time
from typing import TYPE_CHECKING, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk

from src.i18n import _
from src.ui.windows.base import WindowBase

if TYPE_CHECKING:
    pass

# D-Bus signals that mean "the session is being locked or the machine is going to sleep".
# (bus, interface, member, whether the first argument must be true)
SYSTEM_LOCK_SIGNALS = (
    (Gio.BusType.SYSTEM, "org.freedesktop.login1.Manager", "PrepareForSleep", True),
    (Gio.BusType.SYSTEM, "org.freedesktop.login1.Session", "Lock", False),
    (Gio.BusType.SESSION, "org.gnome.ScreenSaver", "ActiveChanged", True),
    (Gio.BusType.SESSION, "org.freedesktop.ScreenSaver", "ActiveChanged", True),
)

IDLE_LOCK_ENV = "GOSSIP_IDLE_LOCK_SECONDS"
DEFAULT_IDLE_LOCK_SECONDS = 300
REVEAL_ENV = "GOSSIP_REVEAL_SECONDS"
DEFAULT_REVEAL_SECONDS = 120
HIDE_ON_BLUR_ENV = "GOSSIP_HIDE_ON_BLUR"


def idle_lock_seconds() -> int:
    """Return the configured inactivity timeout in seconds (0 disables the lock).

    Reads GOSSIP_IDLE_LOCK_SECONDS; invalid values fall back to the default.

    Returns:
        int: Seconds of inactivity before secrets are hidden, or 0 when disabled.
    """
    raw = os.environ.get(IDLE_LOCK_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_IDLE_LOCK_SECONDS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_IDLE_LOCK_SECONDS


def reveal_seconds() -> int:
    """Return how long a revealed value stays visible, in seconds (0 keeps it until hidden).

    Reads GOSSIP_REVEAL_SECONDS; invalid values fall back to the default.
    """
    raw = os.environ.get(REVEAL_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_REVEAL_SECONDS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_REVEAL_SECONDS


def hide_on_blur() -> bool:
    """True when GOSSIP_HIDE_ON_BLUR asks to hide revealed values as the window loses focus."""
    return os.environ.get(HIDE_ON_BLUR_ENV, "").strip().lower() in ("1", "true", "yes", "on")


class WindowIdleLockMixin(WindowBase):
    """Hides the payload, clears it from memory and wipes the clipboard after inactivity."""

    _idle_seconds: int = 0
    _idle_locked: bool = False
    _idle_timer_id: Optional[int] = None
    _compare_dialog: Optional[Gtk.Window] = None
    _last_activity: float = 0.0
    _reveal_timer_id: Optional[int] = None

    def _show_toast(self, text: str) -> None: ...  # Defined in WindowNavMixin
    def _load_secrets_async(self) -> None: ...  # Defined in WindowDataMixin
    def _on_change_context_clicked(self, _btn: Optional[Gtk.Button]) -> None: ...  # WindowNavMixin
    def _cancel_clipboard_clear(self) -> None: ...  # Defined in WindowActionsMixin
    def _reset_payload(self) -> None: ...
    def _render_payload_text(self) -> None: ...

    def _setup_idle_lock(self) -> None:
        """Install input listeners and start the inactivity timer (no-op when disabled)."""
        self._idle_seconds = idle_lock_seconds()
        self._idle_locked = False
        self._idle_timer_id = None
        self._setup_system_lock()

        key = Gtk.EventControllerKey()
        key.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        key.connect("key-pressed", self._on_key_activity)

        motion = Gtk.EventControllerMotion()
        motion.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        motion.connect("motion", lambda *_args: self._on_user_activity())

        click = Gtk.GestureClick()
        click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        click.connect("pressed", lambda *_args: self._on_user_activity())

        scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
        scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        scroll.connect("scroll", self._on_key_activity)

        for controller in (key, motion, click, scroll):
            self.add_controller(controller)

        self._on_user_activity()
        self.connect("notify::is-active", self._on_active_changed)

    def _on_active_changed(self, *_args: object) -> None:
        """Hide a revealed value when the window loses focus (opt-in)."""
        if not self.is_active() and hide_on_blur():
            self._hide_revealed(_("Secret hidden because the window lost focus"))

    def _arm_reveal_timer(self) -> None:
        """Start the countdown that hides the value again (once per reveal)."""
        seconds = reveal_seconds()
        if seconds > 0 and self._reveal_timer_id is None:
            self._reveal_timer_id = GLib.timeout_add_seconds(seconds, self._on_reveal_expired)

    def _cancel_reveal_timer(self) -> None:
        """Stop the countdown, if any."""
        if self._reveal_timer_id is not None:
            GLib.source_remove(self._reveal_timer_id)
            self._reveal_timer_id = None

    def _on_reveal_expired(self) -> bool:
        """Timer callback: hide the value and forget it."""
        self._reveal_timer_id = None
        self._hide_revealed(_("Secret hidden automatically"))
        return GLib.SOURCE_REMOVE

    def _hide_revealed(self, message: str) -> None:
        """Hide and drop a revealed value, telling the user why. Does nothing when it is hidden."""
        if not self.is_payload_revealed:
            return
        self.state.hide_payload()
        self._render_payload_text()
        self._show_toast(message)

    def _setup_system_lock(self) -> None:
        """Lock when the screen locks or the machine suspends (Linux and BSD, via D-Bus).

        Platforms without these buses (macOS, Windows) simply do not subscribe; the
        inactivity timer still applies there.
        """
        self._system_lock_connections: list = []
        for bus_type, interface, member, needs_true in SYSTEM_LOCK_SIGNALS:
            try:
                connection = Gio.bus_get_sync(bus_type, None)
                connection.signal_subscribe(
                    None,
                    interface,
                    member,
                    None,
                    None,
                    Gio.DBusSignalFlags.NONE,
                    self._on_system_lock_signal,
                    needs_true,
                )
            except GLib.Error:
                continue
            self._system_lock_connections.append(connection)

    def _on_system_lock_signal(
        self,
        _connection: Gio.DBusConnection,
        _sender: Optional[str],
        _path: str,
        _interface: str,
        _signal: str,
        parameters: GLib.Variant,
        needs_true: bool,
    ) -> None:
        """Hide and forget secrets as soon as the session locks or the system suspends."""
        if needs_true:
            values = parameters.unpack()
            if not values or not values[0]:
                return
        if not self._idle_locked:
            self._lock_after_idle(by_session=True)

    def _on_key_activity(self, *_args: object) -> bool:
        """Count a key press or scroll as activity without consuming the event."""
        self._on_user_activity()
        return False

    def _on_user_activity(self) -> None:
        """Record user input, reload the payload if it was locked and make sure a timer runs."""
        self._last_activity = time.monotonic()
        if self._idle_locked:
            self._unlock_after_idle()
        if self._idle_timer_id is None and self._idle_seconds > 0:
            self._idle_timer_id = GLib.timeout_add_seconds(self._idle_seconds, self._check_idle)

    def _check_idle(self) -> bool:
        """Lock if the inactivity period elapsed, otherwise wait for the remaining time."""
        self._idle_timer_id = None
        remaining = self._idle_seconds - (time.monotonic() - self._last_activity)
        if remaining <= 0:
            self._lock_after_idle()
        else:
            self._idle_timer_id = GLib.timeout_add_seconds(
                max(1, math.ceil(remaining)), self._check_idle
            )
        return GLib.SOURCE_REMOVE

    def _lock_after_idle(self, by_session: bool = False) -> None:
        """Hide and forget the secret value, and wipe the clipboard if Gossip owns it."""
        self._idle_locked = True
        self._cancel_reveal_timer()
        self._reset_payload()
        self.text_buffer.set_text(
            _("[Hidden: session locked]") if by_session else _("[Hidden after inactivity]")
        )
        self.copy_val_btn.set_sensitive(False)

        if self._compare_dialog is not None:
            self._compare_dialog.close()
            self._compare_dialog = None

        for provider in self.providers.values():
            provider.lock()

        self._cancel_clipboard_clear()
        display = Gdk.Display.get_default()
        if display:
            clipboard = display.get_clipboard()
            if clipboard.is_local():
                clipboard.set_content(None)
        self._show_toast(
            _("Secret hidden because the session was locked")
            if by_session
            else _("Secret hidden after inactivity")
        )

    def _unlock_after_idle(self) -> None:
        """Show the masked placeholder again; the value is fetched only if the user asks."""
        self._idle_locked = False
        self._render_payload_text()
        self.copy_val_btn.set_sensitive(bool(self.current_versions))
        self._reopen_locked_vault()

    def _reopen_locked_vault(self) -> None:
        """Ask for the vault password again (or re-read its private file) after a lock."""
        provider = self.active_provider
        if provider.provider_id != "ansible" or getattr(provider, "is_unlocked", True):
            return
        if getattr(provider, "password_file", None):
            self._load_secrets_async()
        else:
            self._on_change_context_clicked(None)
