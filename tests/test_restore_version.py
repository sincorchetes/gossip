from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from src.i18n import set_language
from src.models import SecretItem, SecretVersionItem
from src.readonly import ENV_VAR
from tests.test_window import DummySyncThread
from tests.window_case import WindowCase


def versions():
    return [
        SecretVersionItem(version_id="3", name="s@3", state="ENABLED"),
        SecretVersionItem(version_id="2", name="s@2", state="ENABLED"),
        SecretVersionItem(version_id="1", name="s@1", state="DESTROYED"),
        SecretVersionItem(version_id="0", name="s@0", state="DISABLED"),
    ]


def buttons(widget):
    found = []
    child = widget.get_first_child()
    while child:
        if isinstance(child, Gtk.Button):
            found.append(child)
        found.extend(buttons(child))
        child = child.get_next_sibling()
    return found


class TestRestoreButtons(WindowCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        patcher = patch.dict(os.environ, {ENV_VAR: "0"})
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.window.selected_secret = SecretItem(name="s", secret_id="s")

    def restore_buttons(self, provider):
        self.window.active_provider = provider
        self.window._render_versions_list(versions())
        return [
            b
            for b in buttons(self.window.versions_list_box)
            if "Restore" in (b.get_tooltip_text() or "")
        ]

    def test_only_older_readable_versions_can_be_restored(self):
        restore = self.restore_buttons(self.mock_aws)
        self.assertEqual(
            [b.get_tooltip_text() for b in restore], ["Restore version 2 as the current version"]
        )

    def test_no_button_when_the_provider_has_no_history(self):
        self.mock_aws.supports_version_restore = False
        self.assertEqual(self.restore_buttons(self.mock_aws), [])

    def test_no_button_in_read_only_mode(self):
        with patch.dict(os.environ, {ENV_VAR: "1"}):
            self.assertEqual(self.restore_buttons(self.mock_aws), [])


class TestRestoreFlow(WindowCase):
    def setUp(self):
        super().setUp()
        set_language("en")
        self.addCleanup(set_language, "es")
        self.window.selected_secret = SecretItem(name="projects/p/secrets/s", secret_id="s")
        self.window.active_provider = self.mock_aws
        self.version = SecretVersionItem(version_id="2", name="s@2", state="ENABLED")

    def run_restore(self):
        with (
            patch.object(self.window.dialogs, "confirm_restore") as dialog,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
            patch.object(self.window, "_show_toast") as toast,
            patch.object(self.window, "_load_versions_async") as reload,
        ):
            self.window._on_restore_version_clicked(self.version)
            dialog.assert_called_once()
            self.assertEqual(dialog.call_args.args[1], "2")
            dialog.call_args.args[2]()
        return toast, reload

    def test_the_old_value_is_written_as_a_new_version(self):
        self.mock_aws.access_secret_payload.return_value = ("old value", False)
        toast, reload = self.run_restore()
        self.mock_aws.access_secret_payload.assert_called_once_with("s@2")
        self.mock_aws.add_secret_version.assert_called_once_with(
            "projects/p/secrets/s", "old value"
        )
        reload.assert_called_once_with("projects/p/secrets/s")
        self.assertIn("restored", toast.call_args.args[0])

    def test_errors_are_reported_and_nothing_is_written(self):
        self.mock_aws.access_secret_payload.side_effect = RuntimeError("denied")
        toast, reload = self.run_restore()
        self.mock_aws.add_secret_version.assert_not_called()
        reload.assert_not_called()
        self.assertIn("denied", toast.call_args.args[0])

    def test_nothing_happens_without_a_selected_secret(self):
        self.window.selected_secret = None
        with patch.object(self.window.dialogs, "confirm_restore") as dialog:
            self.window._on_restore_version_clicked(self.version)
        dialog.assert_not_called()

    def test_read_only_mode_blocks_it(self):
        with (
            patch.dict(os.environ, {ENV_VAR: "1"}),
            patch.object(self.window.dialogs, "confirm_restore") as dialog,
        ):
            self.window._on_restore_version_clicked(self.version)
        dialog.assert_not_called()

    def test_it_is_audited(self):
        from src import audit

        with (
            patch.dict(os.environ, {audit.ENV_VAR: "1"}),
            patch.object(self.window, "_show_toast"),
            patch.object(self.window, "_load_versions_async"),
        ):
            self.window._on_version_restored_success(self.window.selected_secret, "2")
        import json

        with open(audit.default_path(), encoding="utf-8") as handle:
            event = json.loads(handle.readline())
        self.assertEqual((event["action"], event["version"]), ("restore_version", "2"))

    def test_restored_success_without_matching_selection(self):
        self.window.selected_secret = None
        with (
            patch.object(self.window, "_show_toast"),
            patch.object(self.window, "_load_versions_async") as load,
        ):
            self.window._on_version_restored_success(SecretItem(name="s", secret_id="s"), "2")
        load.assert_not_called()


class TestDestroyedVersionButtons(WindowCase):
    def test_destroyed_version_has_no_toggle_buttons(self):
        box = Gtk.Box()
        with patch.dict(os.environ, {ENV_VAR: "0"}):
            self.window._create_version_action_buttons(
                box, SecretVersionItem(version_id="1", name="s@1", state="DESTROYED")
            )
        icons = [b.get_icon_name() for b in buttons(box)]
        self.assertNotIn("media-playback-pause-symbolic", icons)
        self.assertNotIn("media-playback-start-symbolic", icons)


class TestRestoreDialog(unittest.TestCase):
    def test_confirm_only_on_restore(self):
        from gi.repository import Adw

        from src.ui.dialogs import show_confirm_restore_version_dialog

        for response, expected in (("restore", True), ("cancel", False)):
            created = []
            original = Adw.MessageDialog.__init__

            def capture(dialog_self, *args, **kwargs):
                original(dialog_self, *args, **kwargs)
                created.append(dialog_self)

            on_confirm = MagicMock()
            with patch.object(Adw.MessageDialog, "__init__", capture):
                show_confirm_restore_version_dialog(Gtk.Window(), "5", on_confirm)
            created[0].emit("response", response)
            self.assertEqual(on_confirm.called, expected)


if __name__ == "__main__":
    unittest.main()
