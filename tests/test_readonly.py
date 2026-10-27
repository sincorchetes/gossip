from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.i18n import set_language
from src.models import SecretItem, SecretVersionItem
from src.readonly import (
    ENV_VAR,
    LOCK_VAR,
    blocks_writes,
    is_locked,
    is_read_only,
    set_read_only,
)
from tests.window_case import WindowCase


class TestSwitch(unittest.TestCase):
    def test_values(self):
        for value, expected in (
            ("1", True),
            ("TRUE", True),
            (" yes ", True),
            ("0", False),
            ("", False),
        ):
            with patch.dict(os.environ, {ENV_VAR: value}):
                self.assertEqual(is_read_only(), expected, value)
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(is_read_only())

    def test_decorator(self):
        class Target:
            def __init__(self):
                self.toasts = []
                self.calls = 0

            def _show_toast(self, text):
                self.toasts.append(text)

            @blocks_writes
            def write(self, value):
                self.calls += 1
                return value

        target = Target()
        with patch.dict(os.environ, {ENV_VAR: ""}):
            self.assertEqual(target.write(5), 5)
        with patch.dict(os.environ, {ENV_VAR: "1"}):
            self.assertIsNone(target.write(5))
        self.assertEqual((target.calls, len(target.toasts)), (1, 1))

    def test_main_flag_sets_the_switch(self):
        from src.main import main

        with (
            patch("src.ui.app.run_app", return_value=0),
            patch.dict(os.environ, {"DISPLAY": ":0"}),
            patch.object(sys, "argv", ["gossip", "--read-only"]),
        ):
            os.environ.pop(ENV_VAR, None)
            os.environ.pop(LOCK_VAR, None)
            main()
            self.assertEqual(os.environ[ENV_VAR], "1")
            self.assertEqual(os.environ[LOCK_VAR], "1")
            os.environ.pop(ENV_VAR, None)
            os.environ.pop(LOCK_VAR, None)


class TestReadOnlyWindow(WindowCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        patcher = patch.dict(os.environ, {ENV_VAR: "1"})
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_write_buttons_are_hidden(self):
        w = self.window
        for button in (
            w.add_secret_btn,
            w.create_first_btn,
            w.add_version_btn,
            w.delete_secret_btn,
        ):
            self.assertFalse(button.get_visible())

    def test_subtitle_says_read_only(self):
        self.assertIn("read-only", self.window._get_context_subtitle())

    def test_transfer_menu_only_offers_export(self):
        self.assertEqual(self.window.transfer_menu.get_n_items(), 1)

    def test_every_write_is_blocked(self):
        w = self.window
        w.selected_secret = SecretItem(name="n", secret_id="s")
        version = SecretVersionItem(version_id="1", name="n@1")
        with (
            patch.object(w, "_show_toast") as toast,
            patch.object(self.window.dialogs, "create_secret") as create,
            patch.object(self.window.dialogs, "add_version") as add,
            patch.object(self.window.dialogs, "confirm_delete") as delete,
            patch.object(self.window.dialogs, "confirm_destroy") as destroy,
            patch("gi.repository.Gtk.FileDialog") as file_dialog,
        ):
            w._on_create_secret_clicked()
            w._on_add_version_clicked()
            w._on_delete_secret_clicked()
            w._on_destroy_version_clicked(version)
            w._on_toggle_version_state(version, True)
            w._on_import_secrets()
        for dialog in (create, add, delete, destroy, file_dialog):
            dialog.assert_not_called()
        self.assertEqual(toast.call_count, 6)
        self.assertIn("Read-only", toast.call_args.args[0])
        self.mock_gcp.delete_secret.assert_not_called()

    def test_version_rows_have_no_action_buttons(self):
        box = MagicMock()
        self.window._create_version_action_buttons(box, SecretVersionItem(version_id="1", name="n"))
        box.append.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class TestToggleButton(WindowCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        patcher = patch.dict(os.environ, {ENV_VAR: "0"})
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_toggle_blocks_and_restores_every_write_control(self):
        w = self.window
        controls = (w.add_secret_btn, w.create_first_btn, w.add_version_btn, w.delete_secret_btn)
        self.assertFalse(w.read_only_btn.get_active())
        self.assertTrue(all(c.get_visible() for c in controls))
        self.assertEqual(w.transfer_menu.get_n_items(), 2)

        with patch.object(w, "_show_toast") as toast:
            w.read_only_btn.set_active(True)
            self.assertTrue(is_read_only())
            self.assertFalse(any(c.get_visible() for c in controls))
            self.assertEqual(w.transfer_menu.get_n_items(), 1)
            self.assertIn("read-only", w.window_title.get_subtitle())
            self.assertIn("on", w.read_only_btn.get_tooltip_text())
            toast.assert_called_with("Read-only mode enabled")

            w.read_only_btn.set_active(False)
            self.assertFalse(is_read_only())
            self.assertTrue(all(c.get_visible() for c in controls))
            self.assertEqual(w.transfer_menu.get_n_items(), 2)
            self.assertNotIn("read-only", w.window_title.get_subtitle())
            toast.assert_called_with("Read-only mode disabled")

    def test_version_rows_follow_the_toggle(self):
        w = self.window
        w.current_versions = [SecretVersionItem(version_id="1", name="n@1", state="ENABLED")]
        w.mock_provider = self.mock_azure
        w.active_provider = self.mock_azure
        w._render_versions_list(w.current_versions)
        with patch.object(w, "_show_toast"), patch.object(w, "_render_versions_list") as render:
            w.read_only_btn.set_active(True)
        render.assert_called_once_with(w.current_versions)

    def test_set_read_only(self):
        from src.readonly import set_read_only

        set_read_only(True)
        self.assertTrue(is_read_only())
        set_read_only(False)
        self.assertFalse(is_read_only())


class TestLockedByFlag(WindowCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        patcher = patch.dict(os.environ, {ENV_VAR: "1", LOCK_VAR: "1"})
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_the_switch_cannot_be_turned_off(self):
        self.assertTrue(is_locked())
        set_read_only(False)
        self.assertTrue(is_read_only())

    def test_the_toggle_is_disabled_and_explains_why(self):
        button = self.window.read_only_btn
        self.assertFalse(button.get_sensitive())
        self.assertTrue(button.get_active())
        self.assertIn("--read-only", button.get_tooltip_text())

    def test_forcing_the_toggle_off_does_not_unblock_writes(self):
        self.window.read_only_btn.set_active(False)
        self.assertTrue(self.window.read_only_btn.get_active())
        self.assertTrue(is_read_only())
        self.assertFalse(self.window.add_secret_btn.get_visible())

    def test_environment_variable_alone_does_not_lock(self):
        with patch.dict(os.environ, {LOCK_VAR: ""}):
            self.assertFalse(is_locked())
            set_read_only(False)
            self.assertFalse(is_read_only())
