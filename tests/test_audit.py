from __future__ import annotations

import json
import os
import stat
import sys
import unittest
from unittest.mock import patch

from src import audit, state
from src.models import SecretItem, SecretVersionItem
from tests.window_case import WindowCase


def events(path):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


class TestAuditModule(unittest.TestCase):
    def test_off_by_default_and_for_falsy_values(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(audit.ENV_VAR, None)
            self.assertIsNone(audit.active_path())
            audit.record("copy", "gcp")
        for value in ("0", "off", "False", " "):
            with patch.dict(os.environ, {audit.ENV_VAR: value}):
                self.assertIsNone(audit.active_path())
        self.assertFalse(os.path.exists(audit.default_path()))

    def test_enabled_writes_to_the_default_or_a_given_file(self):
        with patch.dict(os.environ, {audit.ENV_VAR: "1"}):
            self.assertEqual(audit.active_path(), audit.default_path())
        self.assertEqual(os.path.dirname(audit.default_path()), os.path.dirname(state.state_path()))
        custom = os.path.join(os.path.dirname(state.state_path()), "custom.log")
        with patch.dict(os.environ, {audit.ENV_VAR: custom}):
            audit.record("reveal", "aws", "AWS: dev (eu-west-1)", secret="prod/db", version="3")
        (event,) = events(custom)
        self.assertEqual(
            (event["action"], event["provider"], event["secret"], event["version"]),
            ("reveal", "aws", "prod/db", "3"),
        )
        self.assertIn("T", event["time"])
        if sys.platform != "win32":
            self.assertEqual(stat.S_IMODE(os.stat(custom).st_mode), 0o600)

    def test_values_never_reach_the_file(self):
        with patch.dict(os.environ, {audit.ENV_VAR: "1"}):
            audit.record(
                "create", "vault", secret="s", value="hunter2", payload="x", Password="p", n=2
            )
        (event,) = events(audit.default_path())
        self.assertEqual(event["n"], 2)
        for forbidden in ("value", "payload", "Password"):
            self.assertNotIn(forbidden, event)
        self.assertNotIn("hunter2", open(audit.default_path()).read())

    def test_file_is_rotated_when_large(self):
        with patch.dict(os.environ, {audit.ENV_VAR: "1"}):
            audit.record("a", "gcp")
            with patch.object(audit, "MAX_BYTES", 1):
                audit.record("b", "gcp")
        self.assertEqual([e["action"] for e in events(audit.default_path() + ".1")], ["a"])
        self.assertEqual([e["action"] for e in events(audit.default_path())], ["b"])

    def test_write_failures_are_swallowed(self):
        with patch.dict(os.environ, {audit.ENV_VAR: "1"}), patch("os.open", side_effect=OSError):
            audit.record("a", "gcp")
        with patch.object(audit.os.path, "getsize", side_effect=OSError):
            audit._rotate("/nonexistent")


class TestWindowAudits(WindowCase):
    def setUp(self):
        patcher = patch.dict(os.environ, {audit.ENV_VAR: "1"})
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()
        self.window.selected_secret = SecretItem(name="n", secret_id="sec")

    def actions(self):
        return [e["action"] for e in events(audit.default_path())]

    def test_lifecycle_events(self):
        w = self.window
        with (
            patch.object(w, "_show_toast"),
            patch.object(w, "_load_secrets_async"),
            patch.object(w, "_load_versions_async"),
        ):
            w._on_secret_created_success("new")
            w._on_version_added_success()
            w._on_version_state_changed_success("2", True)
            w._on_version_state_changed_success("2", False)
            w._on_version_destroyed_success("2")
            w._on_secret_deleted_success("sec", True)
        self.assertEqual(
            self.actions(),
            [
                "create",
                "add_version",
                "enable_version",
                "disable_version",
                "destroy_version",
                "delete",
            ],
        )
        last = events(audit.default_path())[-1]
        self.assertEqual((last["secret"], last["recoverable"]), ("sec", True))

    def test_reveal_and_copy_are_recorded_without_the_value(self):
        w = self.window
        w._payload_pending = "reveal"
        w.current_versions = [SecretVersionItem(version_id="1", name="n@1")]
        with patch.object(w, "_render_payload_text"):
            w._on_payload_loaded("TOP-SECRET-VALUE", False, None, w.active_provider.provider_id)
        with patch("gi.repository.Gdk.Display.get_default"), patch.object(w, "_show_toast"):
            w._copy_payload_to_clipboard("TOP-SECRET-VALUE")
        self.assertEqual(self.actions(), ["reveal", "copy"])
        self.assertNotIn("TOP-SECRET-VALUE", open(audit.default_path()).read())

    def test_import_and_export_are_recorded(self):
        from src.transfer import ImportResult

        w = self.window
        w.secrets = [SecretItem(name="a", secret_id="a")]
        with patch.object(w, "_show_toast"), patch("threading.Thread"):
            w._start_export("/tmp/x.json", True)
        with (
            patch.object(self.window.dialogs, "import_result"),
            patch.object(w, "_load_secrets_async"),
        ):
            w._on_import_done(ImportResult(created=["a"], skipped=["b"], failed=[]), None)
        export, imported = events(audit.default_path())
        self.assertEqual(
            (export["action"], export["count"], export["with_data"]), ("export", 1, True)
        )
        self.assertEqual((imported["created"], imported["skipped"]), (1, 1))


class TestMainFlag(unittest.TestCase):
    def test_audit_log_flag(self):
        from src.main import main

        for argv, expected in (
            (["gossip", "--audit-log"], "1"),
            (["gossip", "--audit-log", "/tmp/a.log"], "/tmp/a.log"),
        ):
            with (
                patch("src.ui.app.run_app", return_value=0),
                patch.dict(os.environ, {"DISPLAY": ":0"}),
                patch.object(sys, "argv", argv),
            ):
                os.environ.pop(audit.ENV_VAR, None)
                main()
                self.assertEqual(os.environ[audit.ENV_VAR], expected)
                os.environ.pop(audit.ENV_VAR, None)


if __name__ == "__main__":
    unittest.main()
