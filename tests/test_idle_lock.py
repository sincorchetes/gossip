from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from src.i18n import set_language
from src.models import SecretVersionItem
from src.ui.windows import idle
from src.ui.windows.idle import DEFAULT_IDLE_LOCK_SECONDS, idle_lock_seconds
from tests.window_case import WindowCase


class TestIdleLockSeconds(unittest.TestCase):
    def _value(self, raw):
        env = {} if raw is None else {idle.IDLE_LOCK_ENV: raw}
        with patch.dict("os.environ", env, clear=True):
            return idle_lock_seconds()

    def test_default_when_unset_or_blank(self):
        self.assertEqual(self._value(None), DEFAULT_IDLE_LOCK_SECONDS)
        self.assertEqual(self._value("  "), DEFAULT_IDLE_LOCK_SECONDS)

    def test_custom_zero_and_negative_values(self):
        self.assertEqual(self._value("45"), 45)
        self.assertEqual(self._value("0"), 0)
        self.assertEqual(self._value("-5"), 0)

    def test_invalid_value_falls_back_to_default(self):
        self.assertEqual(self._value("soon"), DEFAULT_IDLE_LOCK_SECONDS)


class TestIdleLockBehaviour(WindowCase):
    def test_lock_hides_and_forgets_the_secret(self):
        self.window.current_payload = "super-secret"
        self.window.is_payload_revealed = True
        clipboard = MagicMock()
        clipboard.is_local.return_value = True
        display = MagicMock()
        display.get_clipboard.return_value = clipboard

        with patch("gi.repository.Gdk.Display.get_default", return_value=display):
            self.window._lock_after_idle()

        self.assertIsNone(self.window.current_payload)
        self.assertFalse(self.window.is_payload_revealed)
        self.assertTrue(self.window._idle_locked)
        clipboard.set_content.assert_called_once_with(None)
        self.assertFalse(self.window.copy_val_btn.get_sensitive())

    def test_lock_leaves_foreign_clipboard_content_alone(self):
        clipboard = MagicMock()
        clipboard.is_local.return_value = False
        display = MagicMock()
        display.get_clipboard.return_value = clipboard
        with patch("gi.repository.Gdk.Display.get_default", return_value=display):
            self.window._lock_after_idle()
        clipboard.set_content.assert_not_called()

    def test_lock_without_display_does_not_fail(self):
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self.window._lock_after_idle()
        self.assertTrue(self.window._idle_locked)

    def test_activity_after_lock_shows_placeholder_without_fetching(self):
        self.window.current_versions = [SecretVersionItem(version_id="1", name="v1")]
        self.window._idle_locked = True

        with patch.object(self.window, "_load_payload_async") as mock_load:
            self.window._on_user_activity()

        self.assertFalse(self.window._idle_locked)
        mock_load.assert_not_called()
        self.assertTrue(self.window.copy_val_btn.get_sensitive())
        self.assertIsNone(self.window.current_payload)

    def test_unlock_without_versions_keeps_copy_disabled(self):
        self.window.current_versions = []
        self.window._unlock_after_idle()
        self.assertFalse(self.window.copy_val_btn.get_sensitive())

    def test_lock_invalidates_pending_value_requests(self):
        before = self.window._payload_request_id
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self.window._lock_after_idle()
        self.assertGreater(self.window._payload_request_id, before)

    def test_check_idle_locks_when_period_elapsed(self):
        self.window._idle_seconds = 10
        self.window._last_activity = time.monotonic() - 11
        with patch.object(self.window, "_lock_after_idle") as mock_lock:
            self.assertFalse(self.window._check_idle())
        mock_lock.assert_called_once()

    def test_check_idle_reschedules_for_remaining_time(self):
        self.window._idle_seconds = 10
        self.window._last_activity = time.monotonic() - 4
        with (
            patch.object(self.window, "_lock_after_idle") as mock_lock,
            patch.object(idle.GLib, "timeout_add_seconds", return_value=7) as mock_timer,
        ):
            self.window._check_idle()
        mock_lock.assert_not_called()
        self.assertEqual(self.window._idle_timer_id, 7)
        self.assertIn(mock_timer.call_args[0][0], (6, 7))

    def test_activity_starts_a_timer_when_none_is_pending(self):
        self.window._idle_seconds = 30
        self.window._idle_timer_id = None
        with patch.object(idle.GLib, "timeout_add_seconds", return_value=9) as mock_timer:
            self.window._on_user_activity()
        mock_timer.assert_called_once_with(30, self.window._check_idle)
        self.assertEqual(self.window._idle_timer_id, 9)

    def test_disabled_timer_still_listens_for_activity_but_never_schedules(self):
        # The controllers stay so the window can unlock after a session lock
        with patch.dict("os.environ", {idle.IDLE_LOCK_ENV: "0"}):
            with patch.object(self.window, "add_controller") as mock_add:
                self.window._setup_idle_lock()
        self.assertEqual(mock_add.call_count, 4)
        self.assertIsNone(self.window._idle_timer_id)

    def test_enabled_lock_installs_input_controllers(self):
        with patch.dict("os.environ", {idle.IDLE_LOCK_ENV: "60"}):
            with patch.object(self.window, "add_controller") as mock_add:
                self.window._setup_idle_lock()
        self.assertEqual(mock_add.call_count, 4)
        self.assertEqual(self.window._idle_seconds, 60)


class TestVaultLockOnIdle(WindowCase):
    def test_locking_asks_every_provider_to_forget_its_secrets(self):
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self.window._lock_after_idle()
        for provider in self.window.providers.values():
            provider.lock.assert_called_once()

    def test_returning_to_a_locked_ansible_vault_prompts_for_the_password(self):
        self.window.active_provider = self.mock_ansible
        self.mock_ansible.is_unlocked = False
        self.mock_ansible.password_file = None
        with (
            patch.object(self.window, "_on_change_context_clicked") as prompt,
            patch.object(self.window, "_load_secrets_async") as reload,
        ):
            self.window._unlock_after_idle()
        prompt.assert_called_once_with(None)
        reload.assert_not_called()

    def test_returning_with_a_password_file_reloads_without_prompting(self):
        self.window.active_provider = self.mock_ansible
        self.mock_ansible.is_unlocked = False
        self.mock_ansible.password_file = "/home/me/.vault_pass"
        with (
            patch.object(self.window, "_on_change_context_clicked") as prompt,
            patch.object(self.window, "_load_secrets_async") as reload,
        ):
            self.window._unlock_after_idle()
        reload.assert_called_once()
        prompt.assert_not_called()

    def test_unlocked_vault_or_other_providers_are_left_alone(self):
        with (
            patch.object(self.window, "_on_change_context_clicked") as prompt,
            patch.object(self.window, "_load_secrets_async") as reload,
        ):
            self.window._unlock_after_idle()  # GCP is active
            self.window.active_provider = self.mock_ansible
            self.mock_ansible.is_unlocked = True
            self.window._unlock_after_idle()
        prompt.assert_not_called()
        reload.assert_not_called()


class TestSystemLock(WindowCase):
    """Lock when the screen locks or the machine goes to sleep."""

    def setUp(self):
        super().setUp()
        set_language("en")
        self.addCleanup(set_language, "es")

    def _signal(self, needs_true, *args):
        from gi.repository import GLib

        params = GLib.Variant("(b)", (args[0],)) if args else GLib.Variant("()", ())
        self.window._on_system_lock_signal(None, None, "/", "i", "s", params, needs_true)

    def test_subscribes_to_every_lock_signal(self):
        connection = MagicMock()
        with patch.object(idle.Gio, "bus_get_sync", return_value=connection):
            self.window._setup_system_lock()
        members = [c.args[2] for c in connection.signal_subscribe.call_args_list]
        self.assertEqual(members, ["PrepareForSleep", "Lock", "ActiveChanged", "ActiveChanged"])
        self.assertEqual(len(self.window._system_lock_connections), 4)

    def test_missing_buses_are_ignored(self):
        from gi.repository import GLib

        with patch.object(idle.Gio, "bus_get_sync", side_effect=GLib.Error("no bus")):
            self.window._setup_system_lock()
        self.assertEqual(self.window._system_lock_connections, [])

    def test_sleep_and_screensaver_start_lock_only_when_true(self):
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self._signal(True, False)
            self.assertFalse(self.window._idle_locked)
            self._signal(True, True)
            self.assertTrue(self.window._idle_locked)

    def test_lock_signal_needs_no_argument(self):
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self._signal(False)
        self.assertTrue(self.window._idle_locked)

    def test_it_hides_the_value_and_says_why(self):
        self.window.current_payload = "secret"
        self.window.is_payload_revealed = True
        with (
            patch("gi.repository.Gdk.Display.get_default", return_value=None),
            patch.object(self.window, "_show_toast") as toast,
        ):
            self._signal(True, True)
        self.assertIsNone(self.window.current_payload)
        self.assertFalse(self.window.is_payload_revealed)
        toast.assert_called_once()
        self.assertIn("session", toast.call_args.args[0].lower())

    def test_an_already_locked_window_is_not_locked_twice(self):
        self.window._idle_locked = True
        with patch.object(self.window, "_lock_after_idle") as lock:
            self._signal(True, True)
        lock.assert_not_called()

    def test_every_provider_forgets_its_secrets(self):
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self._signal(True, True)
        for provider in self.window.providers.values():
            provider.lock.assert_called_once()


if __name__ == "__main__":
    unittest.main()


class TestRevealSettings(unittest.TestCase):
    def _reveal(self, raw):
        env = {} if raw is None else {idle.REVEAL_ENV: raw}
        with patch.dict("os.environ", env, clear=True):
            return idle.reveal_seconds()

    def test_reveal_default_zero_and_invalid_values(self):
        self.assertEqual(self._reveal(None), idle.DEFAULT_REVEAL_SECONDS)
        self.assertEqual(self._reveal("30"), 30)
        self.assertEqual(self._reveal("0"), 0)
        self.assertEqual(self._reveal("-4"), 0)
        self.assertEqual(self._reveal("later"), idle.DEFAULT_REVEAL_SECONDS)

    def test_hide_on_blur_is_opt_in(self):
        for raw, expected in ((None, False), ("", False), ("0", False), ("1", True), ("Yes", True)):
            env = {} if raw is None else {idle.HIDE_ON_BLUR_ENV: raw}
            with patch.dict("os.environ", env, clear=True):
                self.assertIs(idle.hide_on_blur(), expected)


class TestRevealedValueHiding(WindowCase):
    def _reveal(self):
        self.window.current_payload = "super-secret"
        self.window.is_payload_revealed = True
        self.window._render_payload_text()

    def test_revealing_starts_one_timer_and_hiding_stops_it(self):
        with patch.dict("os.environ", {idle.REVEAL_ENV: "60"}):
            self._reveal()
            first = self.window._reveal_timer_id
            self.assertIsNotNone(first)
            self.window._render_payload_text()  # a re-render does not extend the time
            self.assertEqual(self.window._reveal_timer_id, first)
            self.window.state.hide_payload()
            self.window._render_payload_text()
        self.assertIsNone(self.window._reveal_timer_id)

    def test_a_zero_timeout_keeps_the_value_until_hidden(self):
        with patch.dict("os.environ", {idle.REVEAL_ENV: "0"}):
            self._reveal()
        self.assertIsNone(self.window._reveal_timer_id)
        self.assertTrue(self.window.is_payload_revealed)

    def test_expiry_hides_and_forgets_the_value(self):
        with patch.dict("os.environ", {idle.REVEAL_ENV: "60"}):
            self._reveal()
        self.window._on_reveal_expired()
        self.assertIsNone(self.window.current_payload)
        self.assertFalse(self.window.is_payload_revealed)
        self.assertIsNone(self.window._reveal_timer_id)

    def test_losing_focus_hides_only_when_enabled(self):
        self._reveal()
        with (
            patch.object(self.window, "is_active", return_value=False),
            patch.dict("os.environ", {}, clear=True),
        ):
            self.window._on_active_changed()
        self.assertTrue(self.window.is_payload_revealed)
        with (
            patch.object(self.window, "is_active", return_value=False),
            patch.dict("os.environ", {idle.HIDE_ON_BLUR_ENV: "1"}),
        ):
            self.window._on_active_changed()
        self.assertFalse(self.window.is_payload_revealed)
        self.assertIsNone(self.window.current_payload)

    def test_locking_cancels_the_timer(self):
        with patch.dict("os.environ", {idle.REVEAL_ENV: "60"}):
            self._reveal()
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self.window._lock_after_idle()
        self.assertIsNone(self.window._reveal_timer_id)
