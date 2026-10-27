from __future__ import annotations

import logging
import os
import unittest
from unittest.mock import patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src import diagnostics, log
from src.ui.dialogs import show_about_dialog


class TestRedaction(unittest.TestCase):
    def test_credentials_and_home_are_removed(self):
        home = os.path.expanduser("~")
        cases = {
            "token=abc123def": "token=***",
            "Password: hunter2": "Password: ***",
            "X-Vault-Token: s.abcdefg": "X-Vault-Token: ***",
            "Authorization: Bearer eyJhbGciOi.payload.sig": "Authorization: ***",
            "Authorization: Basic dXNlcjpwYXNz": "Authorization: ***",
            "https://user:pw@vault.example.com/v1": "https://***@vault.example.com/v1",
            "key " + "A" * 40 + " end": "key *** end",
            f"reading {home}/.vault-token": "reading ~/.vault-token",
            "api_key=zzz and secret = yyy": "api_key=*** and secret = ***",
        }
        for raw, expected in cases.items():
            self.assertEqual(log.redact(raw), expected, raw)

    def test_harmless_text_is_untouched(self):
        self.assertEqual(log.redact("listed 12 secrets in 0.4s"), "listed 12 secrets in 0.4s")


class TestRing(unittest.TestCase):
    def test_debug_lines_are_kept_redacted_and_bounded_even_without_debug_mode(self):
        logger = log.get_logger("tests.ring")
        logger.debug("password=hunter2 for %s", "demo")
        self.assertIn("password=*** for demo", log.recent_log()[-1])
        for i in range(log.RING_SIZE + 20):
            logger.debug("line %d", i)
        lines = log.recent_log()
        self.assertEqual(len(lines), log.RING_SIZE)
        self.assertIn(f"line {log.RING_SIZE + 19}", lines[-1])

    def test_formatting_errors_do_not_escape(self):
        handler = log.RingHandler(size=3)
        record = logging.LogRecord(
            "gossip.x", logging.DEBUG, __file__, 1, "%d", ("not a number",), None
        )
        with patch.object(handler, "handleError") as handle:
            handler.emit(record)
        handle.assert_called_once()


class TestReport(unittest.TestCase):
    def test_it_lists_versions_settings_and_the_log_but_no_names(self):
        log.get_logger("tests.report").debug("hello from the report test")
        text = diagnostics.build_report("vault", 7)
        for expected in (
            "Gossip ",
            "Python ",
            "System: ",
            "GTK ",
            "Language: ",
            "provider: vault (of 7)",
            "read-only: ",
            "idle lock seconds: ",
            "audit log: ",
            "boto3: ",
            "hello from the report test",
        ):
            self.assertIn(expected, text)
        self.assertNotIn("project", text.lower().replace("projects", ""))

    def test_unknown_provider_and_missing_packages_are_reported(self):
        with patch.object(
            diagnostics.metadata, "version", side_effect=diagnostics.metadata.PackageNotFoundError
        ):
            text = diagnostics.build_report()
        self.assertIn("provider: unknown (of 0)", text)
        self.assertIn("boto3: not installed", text)

    def test_an_empty_log_is_shown_as_such(self):
        with patch.object(diagnostics, "recent_log", return_value=[]):
            self.assertIn("(empty)", diagnostics.build_report())

    def test_the_toolkit_query_never_breaks_the_report(self):
        with patch("gi.require_version", side_effect=ValueError("no gtk")):
            self.assertIn("unknown", diagnostics._toolkit_versions())

    def test_the_audit_setting_is_reflected(self):
        from src import audit

        with patch.dict(os.environ, {audit.ENV_VAR: "1"}):
            self.assertIn("audit log: on", diagnostics.build_report())


class TestAboutDialogCarriesTheReport(unittest.TestCase):
    def test_debug_info_is_set_without_a_provider_window(self):
        window = Gtk.Window()
        with (
            patch.object(Adw.AboutWindow, "present"),
            patch.object(Adw.AboutWindow, "set_debug_info") as set_info,
            patch.object(Adw.AboutWindow, "set_debug_info_filename") as set_name,
        ):
            show_about_dialog(window)
        self.assertIn("Gossip ", set_info.call_args.args[0])
        set_name.assert_called_once_with("gossip-diagnostics.txt")


if __name__ == "__main__":
    unittest.main()
