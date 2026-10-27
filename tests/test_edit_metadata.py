from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.i18n import set_language
from src.labels import format_labels, parse_labels
from src.models import SecretItem
from src.readonly import ENV_VAR
from src.ui.dialogs import show_edit_metadata_dialog
from tests.test_window import DummySyncThread
from tests.window_case import WindowCase


class TestLabels(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(
            parse_labels("env=prod\nteam = core , tier=1\n\n=x\nnovalue\nempty="),
            {"env": "prod", "team": "core", "tier": "1", "empty": ""},
        )
        self.assertEqual(parse_labels(""), {})
        self.assertEqual(parse_labels("a=b=c"), {"a": "b=c"})

    def test_round_trip(self):
        labels = {"env": "prod", "k": "v w"}
        self.assertEqual(parse_labels(format_labels(labels)), labels)


class TestDialog(unittest.TestCase):
    def open(self, with_description=True):
        on_confirm = MagicMock()
        with patch.object(Adw.MessageDialog, "present"):
            dialog = show_edit_metadata_dialog(
                Gtk.Window(), "db", {"env": "dev"}, "old", with_description, on_confirm
            )
        return dialog, on_confirm

    def test_saving_returns_the_edited_values(self):
        dialog, on_confirm = self.open()
        self.assertEqual(dialog.description_row.get_text(), "old")
        buffer = dialog.text_view.get_buffer()
        self.assertEqual(
            buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True), "env=dev"
        )
        buffer.set_text("env=prod\nteam=core")
        dialog.description_row.set_text("  new  ")
        dialog.emit("response", "save")
        on_confirm.assert_called_once_with({"env": "prod", "team": "core"}, "new")

    def test_cancel_changes_nothing_and_description_is_optional(self):
        dialog, on_confirm = self.open(with_description=False)
        self.assertIsNone(dialog.description_row)
        dialog.emit("response", "cancel")
        on_confirm.assert_not_called()
        dialog.emit("response", "save")
        on_confirm.assert_called_once_with({"env": "dev"}, None)


class TestWindowFlow(WindowCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        patcher = patch.dict(os.environ, {ENV_VAR: "0"})
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.secret = SecretItem(name="projects/p/secrets/db", secret_id="db", labels={"a": "1"})
        self.window.selected_secret = self.secret
        self.provider = self.mock_aws
        self.window.active_provider = self.provider
        self.provider.supports_metadata_edit = True
        self.provider.supports_description_edit = True
        self.provider.load_metadata.return_value = ({"a": "1"}, "desc")

    def run_flow(self):
        with (
            patch.object(self.window.dialogs, "edit_metadata") as dialog,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
            patch.object(self.window, "_show_toast") as toast,
            patch.object(self.window, "_load_secrets_async") as reload,
        ):
            self.window._on_edit_metadata_clicked()
            return dialog, toast, reload

    def test_the_dialog_opens_with_the_current_metadata_and_saving_updates_it(self):
        with (
            patch.object(self.window.dialogs, "edit_metadata") as dialog,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
            patch.object(self.window, "_show_toast") as toast,
            patch.object(self.window, "_load_secrets_async") as reload,
        ):
            self.window._on_edit_metadata_clicked()
            args = dialog.call_args.args
            self.assertEqual(args[1:5], ("db", {"a": "1"}, "desc", True))
            args[5]({"a": "2"}, "new desc")
        self.provider.update_metadata.assert_called_once_with(
            "projects/p/secrets/db", {"a": "2"}, "new desc"
        )
        reload.assert_called_once()
        self.assertIn("saved", toast.call_args.args[0])

    def test_failures_are_reported(self):
        self.provider.load_metadata.side_effect = RuntimeError("no access")
        dialog, toast, _reload = self.run_flow()
        dialog.assert_not_called()
        self.assertIn("no access", toast.call_args.args[0])

        self.provider.load_metadata.side_effect = None
        self.provider.update_metadata.side_effect = RuntimeError("denied")
        with (
            patch.object(self.window.dialogs, "edit_metadata") as dialog,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
            patch.object(self.window, "_show_toast") as toast,
        ):
            self.window._on_edit_metadata_clicked()
            dialog.call_args.args[5]({}, None)
        self.assertIn("denied", toast.call_args.args[0])

    def test_unsupported_providers_and_read_only_do_nothing(self):
        self.provider.supports_metadata_edit = False
        dialog, _toast, _reload = self.run_flow()
        dialog.assert_not_called()
        self.provider.supports_metadata_edit = True
        with patch.dict(os.environ, {ENV_VAR: "1"}):
            dialog, _toast, _reload = self.run_flow()
        dialog.assert_not_called()
        self.window.selected_secret = None
        dialog, _toast, _reload = self.run_flow()
        dialog.assert_not_called()

    def test_button_follows_provider_support_and_read_only(self):
        self.window._update_detail_labels()
        self.assertTrue(self.window.edit_meta_btn.get_visible())
        self.provider.supports_metadata_edit = False
        self.window._update_detail_labels()
        self.assertFalse(self.window.edit_meta_btn.get_visible())
        self.provider.supports_metadata_edit = True
        self.window.read_only_btn.set_active(True)
        self.assertFalse(self.window.edit_meta_btn.get_visible())
        self.window.read_only_btn.set_active(False)
        self.assertTrue(self.window.edit_meta_btn.get_visible())

    def test_it_is_audited(self):
        import json

        from src import audit

        with (
            patch.dict(os.environ, {audit.ENV_VAR: "1"}),
            patch.object(self.window, "_show_toast"),
            patch.object(self.window, "_load_secrets_async"),
        ):
            self.window._on_metadata_saved(self.secret)
        with open(audit.default_path(), encoding="utf-8") as handle:
            self.assertEqual(json.loads(handle.readline())["action"], "edit_metadata")


if __name__ == "__main__":
    unittest.main()
