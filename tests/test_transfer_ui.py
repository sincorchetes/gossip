from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from gi.repository import GLib

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.transfer import ImportResult, TransferEntry
from src.ui.dialogs import transfer as dialogs
from src.ui.windows import transfer as mixin
from tests.window_case import WindowCase


class DummySyncThread:
    def __init__(self, target, *args, **kwargs):
        self.target = target

    def start(self):
        self.target()


def _secret(secret_id):
    return SecretItem(name=f"projects/p/secrets/{secret_id}", secret_id=secret_id)


def _run_sync():
    return (
        patch("threading.Thread", side_effect=DummySyncThread),
        patch.object(mixin.GLib, "idle_add", side_effect=lambda f, *a: f(*a)),
    )


class TestTransferDialogs(WindowCase):
    def _present_patch(self):
        return patch.object(dialogs.Adw.MessageDialog, "present")

    def test_export_dialog_reports_checkbox_choice(self):
        callback = MagicMock()
        with self._present_patch():
            dialog = dialogs.show_export_dialog(self.window, "GCP", 3, callback)
        dialog.get_extra_child().set_active(True)
        dialog.emit("response", "export")
        callback.assert_called_once_with(True)

    def test_export_dialog_defaults_to_no_values_and_ignores_cancel(self):
        callback = MagicMock()
        with self._present_patch():
            dialog = dialogs.show_export_dialog(self.window, "GCP", 3, callback)
        dialog.emit("response", "cancel")
        callback.assert_not_called()
        dialog.emit("response", "export")
        callback.assert_called_once_with(False)

    def test_import_dialog_confirms_and_cancels(self):
        callback = MagicMock()
        entries = [TransferEntry("a", "v"), TransferEntry("b", None)]
        with self._present_patch():
            dialog = dialogs.show_import_dialog(self.window, "AWS", entries, {"a"}, callback)
        self.assertEqual(
            dialog.get_body(),
            _("Import into %s: %d new, %d already exist. %d of the entries include a value.")
            % ("AWS", 1, 1, 1),
        )
        dialog.emit("response", "cancel")
        callback.assert_not_called()
        dialog.emit("response", "import")
        callback.assert_called_once_with("skip")

    def test_import_dialog_can_ask_for_new_versions_of_existing_secrets(self):
        callback = MagicMock()
        with self._present_patch():
            dialog = dialogs.show_import_dialog(
                self.window, "AWS", [TransferEntry("a", "v")], {"a"}, callback
            )
        self.assertTrue(dialog.strategy_row.get_sensitive())
        dialog.strategy_row.set_selected(1)
        dialog.emit("response", "import")
        callback.assert_called_once_with("version")

    def test_strategy_is_disabled_when_nothing_exists_and_long_lists_are_cut(self):
        callback = MagicMock()
        entries = [TransferEntry(f"s{i}", "v") for i in range(250)]
        with self._present_patch():
            dialog = dialogs.show_import_dialog(self.window, "AWS", entries, set(), callback)
        self.assertFalse(dialog.strategy_row.get_sensitive())
        dialog.emit("response", "import")
        callback.assert_called_once_with("skip")

    def test_result_dialog_lists_failures_and_truncates(self):
        failures = [(f"s{i}", "boom") for i in range(8)]
        result = ImportResult(created=["a"], skipped=["b", "c"], failed=failures)
        with self._present_patch():
            dialog = dialogs.show_import_result_dialog(self.window, result)
        body = dialog.get_body()
        self.assertIn("s0: boom", body)
        self.assertNotIn("s7: boom", body)
        self.assertIn("3", body)

    def test_result_dialog_without_failures(self):
        with self._present_patch():
            dialog = dialogs.show_import_result_dialog(self.window, ImportResult(created=["a"]))
        self.assertNotIn("•", dialog.get_body())


class TestExportFlow(WindowCase):
    def test_no_secrets_shows_a_toast(self):
        self.window.secrets = []
        with patch.object(self.window, "_show_toast") as toast:
            self.window._on_export_secrets()
        toast.assert_called_once_with(_("No secrets to export"))

    def test_export_opens_dialog_with_count_and_provider(self):
        self.window.secrets = [_secret("a"), _secret("b")]
        with patch.object(self.window.dialogs, "export") as show:
            self.window._on_export_secrets()
        parent, provider_name, count, callback = show.call_args[0]
        self.assertIs(parent, self.window)
        self.assertEqual((provider_name, count), (self.mock_gcp.display_name, 2))
        self.assertEqual(callback, self.window._choose_export_file)

    def test_choose_file_starts_export_with_selected_path(self):
        gfile = MagicMock()
        gfile.get_path.return_value = "/tmp/out.json"
        file_dialog = MagicMock()
        file_dialog.save_finish.return_value = gfile
        with (
            patch.object(mixin.Gtk, "FileDialog", return_value=file_dialog),
            patch.object(self.window, "_start_export") as start,
        ):
            self.window._choose_export_file(True)
            file_dialog.save.call_args[0][2](file_dialog, MagicMock())
        file_dialog.set_initial_name.assert_called_once_with("gossip-gcp-export.json")
        start.assert_called_once_with("/tmp/out.json", True)

    def test_choose_file_cancelled_or_pathless_does_nothing(self):
        file_dialog = MagicMock()
        with (
            patch.object(mixin.Gtk, "FileDialog", return_value=file_dialog),
            patch.object(self.window, "_start_export") as start,
        ):
            self.window._choose_export_file(False)
            callback = file_dialog.save.call_args[0][2]
            file_dialog.save_finish.side_effect = GLib.Error("cancelled")
            callback(file_dialog, MagicMock())
            file_dialog.save_finish.side_effect = None
            file_dialog.save_finish.return_value = MagicMock(get_path=MagicMock(return_value=None))
            callback(file_dialog, MagicMock())
        start.assert_not_called()

    def test_start_export_writes_file_with_values(self):
        self.window.secrets = [_secret("db")]
        self.mock_gcp.list_versions.return_value = [SecretVersionItem("1", "v1")]
        self.mock_gcp.access_secret_payload.return_value = ("pw", False)
        self.mock_gcp.provider_id = "gcp"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.json")
            patches = _run_sync()
            with patches[0], patches[1], patch.object(self.window, "_show_toast") as toast:
                self.window._start_export(path, True)
            with open(path, encoding="utf-8") as handle:
                document = json.load(handle)
        self.assertEqual(document["secrets"], [{"id": "db", "value": "pw"}])
        self.assertEqual(toast.call_args[0][0], _("Exported %d secrets to %s") % (1, "out.json"))

    def test_export_done_variants(self):
        with patch.object(self.window, "_show_toast") as toast:
            self.window._on_export_done("/x/f.json", 0, [], "disk full")
            self.window._on_export_done("/x/f.json", 3, ["a: denied"], None)
        self.assertEqual(toast.call_args_list[0][0][0], "Error: disk full")
        self.assertEqual(
            toast.call_args_list[1][0][0],
            _("Exported %d secrets to %s (%d without value)") % (3, "f.json", 1),
        )

    def test_export_failure_in_worker_is_reported(self):
        self.window.secrets = [_secret("db")]
        patches = _run_sync()
        with (
            patches[0],
            patches[1],
            patch.object(mixin, "write_export_file", side_effect=OSError("read-only")),
            patch.object(self.window, "_show_toast") as toast,
        ):
            self.window._start_export("/nonexistent/out.json", False)
        self.assertEqual(toast.call_args[0][0], "Error: read-only")


class TestImportFlow(WindowCase):
    def test_choose_file_previews_import(self):
        gfile = MagicMock()
        gfile.get_path.return_value = "/tmp/in.json"
        file_dialog = MagicMock()
        file_dialog.open_finish.return_value = gfile
        with (
            patch.object(mixin.Gtk, "FileDialog", return_value=file_dialog),
            patch.object(self.window, "_start_import_preview") as preview,
        ):
            self.window._on_import_secrets()
            callback = file_dialog.open.call_args[0][2]
            callback(file_dialog, MagicMock())
            file_dialog.open_finish.side_effect = GLib.Error("cancelled")
            callback(file_dialog, MagicMock())
            file_dialog.open_finish.side_effect = None
            file_dialog.open_finish.return_value = None
            callback(file_dialog, MagicMock())
        preview.assert_called_once_with("/tmp/in.json")

    def test_preview_shows_confirmation_and_import_runs_on_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "in.json")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"new": "v", "old": "x"}')
            with patch.object(self.window.dialogs, "import_") as show:
                self.window._start_import_preview(path)
        parent, provider_name, entries, existing_ids, confirm = show.call_args[0]
        self.assertEqual(existing_ids, set())
        self.assertEqual([e.secret_id for e in entries], ["new", "old"])

        self.window.secrets = [_secret("old")]
        patches = _run_sync()
        with (
            patches[0],
            patches[1],
            patch.object(self.window.dialogs, "import_result") as result_dialog,
            patch.object(self.window, "_load_secrets_async") as reload,
            patch.object(self.window, "_show_toast"),
        ):
            confirm("skip")
        self.mock_gcp.create_secret.assert_called_once_with(
            "new", "v", labels=None, description=None
        )
        result = result_dialog.call_args[0][1]
        self.assertEqual((result.created, result.skipped), (["new"], ["old"]))
        reload.assert_called_once()

    def test_invalid_file_shows_error_toast(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "in.json")
            with open(path, "w") as handle:
                handle.write("   ")
            with patch.object(self.window, "_show_toast") as toast:
                self.window._start_import_preview(path)
                self.window._start_import_preview(os.path.join(tmp, "missing.json"))
        self.assertTrue(toast.call_args_list[0][0][0].startswith("Error:"))
        self.assertEqual(toast.call_count, 2)

    def test_nothing_created_does_not_reload(self):
        with (
            patch.object(self.window.dialogs, "import_result"),
            patch.object(self.window, "_load_secrets_async") as reload,
        ):
            self.window._on_import_done(ImportResult(skipped=["a"]), None)
        reload.assert_not_called()

    def test_import_error_is_reported(self):
        with patch.object(self.window, "_show_toast") as toast:
            self.window._on_import_done(ImportResult(), "boom")
        toast.assert_called_once_with("Error: boom")

    def test_unexpected_failure_in_worker_is_reported(self):
        patches = _run_sync()
        with (
            patches[0],
            patches[1],
            patch.object(mixin, "import_entries", side_effect=RuntimeError("bad")),
            patch.object(self.window, "_show_toast") as toast,
        ):
            self.window._start_import([TransferEntry("a")])
        self.assertEqual(toast.call_args[0][0], "Error: bad")


class TestTransferMenu(WindowCase):
    def test_menu_has_both_actions_and_updates_on_language_change(self):
        self.assertEqual(self.window.transfer_menu.get_n_items(), 2)
        self.assertIsNotNone(self.window.lookup_action("export-secrets"))
        self.assertIsNotNone(self.window.lookup_action("import-secrets"))
        self.window._update_transfer_texts()
        self.assertEqual(self.window.transfer_menu.get_n_items(), 2)
        self.assertEqual(self.window.transfer_btn.get_tooltip_text(), _("Import / Export"))


if __name__ == "__main__":
    unittest.main()
