from __future__ import annotations

import contextlib
import importlib
import io
import os
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.main import main
from src.selftest import (
    _CHILD_TIMEOUT_SECONDS,
    _FUNCTIONAL_CHECKS,
    _HEADLESS_ENV,
    _REQUIRED_MODULES,
    _TYPELIB_CHECKS,
    _child_command,
    check_module,
    required_checks,
    run_self_test,
)


def _proc(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestCheckModule(unittest.TestCase):
    def test_successful_import_returns_zero(self):
        self.assertEqual(check_module("yaml"), 0)

    def test_typelib_check_passes_for_available_namespace(self):
        self.assertEqual(check_module("typelib:Gio:2.0"), 0)

    def test_typelib_check_fails_for_missing_namespace(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            self.assertEqual(check_module("typelib:NoSuchLib:9.9"), 1)
        self.assertIn("NoSuchLib", captured.getvalue())

    def test_failed_import_reports_error_on_stderr(self):
        captured = io.StringIO()
        with (
            patch.object(importlib, "import_module", side_effect=ImportError("dlopen failed")),
            contextlib.redirect_stderr(captured),
        ):
            self.assertEqual(check_module("whatever"), 1)
        self.assertIn("ImportError: dlopen failed", captured.getvalue())


class TestRequiredChecks(unittest.TestCase):
    def test_default_checks_include_the_ui_import(self):
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop(_HEADLESS_ENV, None)
            self.assertEqual(required_checks(), _REQUIRED_MODULES + _FUNCTIONAL_CHECKS)

    def test_headless_mode_swaps_ui_import_for_typelib_checks(self):
        with patch.dict("os.environ", {_HEADLESS_ENV: "1"}):
            checks = required_checks()
        self.assertNotIn("src.ui.app", checks)
        self.assertTrue(set(_TYPELIB_CHECKS) <= set(checks))
        self.assertIn("src.providers", checks)


class TestChildCommand(unittest.TestCase):
    def test_development_run_uses_main_script(self):
        command = _child_command("yaml")
        self.assertEqual(command[0], sys.executable)
        self.assertTrue(command[1].endswith("main.py"))
        self.assertEqual(command[-2:], ["--self-test-module", "yaml"])

    def test_frozen_run_reuses_the_executable(self):
        with patch.object(sys, "frozen", True, create=True):
            self.assertEqual(_child_command("yaml"), [sys.executable, "--self-test-module", "yaml"])


class TestRunSelfTest(unittest.TestCase):
    def _run(self, side_effect):
        captured = io.StringIO()
        with (
            patch("subprocess.run", side_effect=side_effect) as mock_run,
            contextlib.redirect_stderr(captured),
        ):
            code = run_self_test()
        return code, captured.getvalue(), mock_run

    def test_all_modules_ok(self):
        code, errors, mock_run = self._run(lambda *a, **k: _proc(0))
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertEqual(mock_run.call_count, len(required_checks()))

    def test_crash_is_attributed_to_the_module_and_does_not_hide_others(self):
        def fake(command, **kwargs):
            module = command[-1]
            if module == "gi":
                return _proc(-11)
            if module == "yaml":
                return _proc(1, stderr="ImportError: no yaml\n")
            return _proc(0)

        code, errors, _ = self._run(fake)
        self.assertEqual(code, 1)
        self.assertIn("FAIL gi: crashed with signal 11", errors)
        self.assertIn("FAIL yaml: exit code 1", errors)
        self.assertIn("ImportError: no yaml", errors)
        self.assertNotIn("FAIL boto3", errors)

    def test_timeout_is_reported(self):
        def fake(command, **kwargs):
            if command[-1] == "boto3":
                raise subprocess.TimeoutExpired(command, _CHILD_TIMEOUT_SECONDS)
            return _proc(0)

        code, errors, _ = self._run(fake)
        self.assertEqual(code, 1)
        self.assertIn("FAIL boto3: timed out", errors)

    def test_real_imports_succeed_in_dev_environment(self):
        self.assertEqual(run_self_test(), 0)


class TestMainFlags(unittest.TestCase):
    def test_self_test_flag_runs_without_display(self):
        with (
            patch.object(sys, "argv", ["gossip", "--self-test"]),
            patch("src.selftest.run_self_test", return_value=0) as mock_run,
        ):
            self.assertEqual(main(), 0)
        mock_run.assert_called_once()

    def test_self_test_module_flag_checks_one_module(self):
        with (
            patch.object(sys, "argv", ["gossip", "--self-test-module", "yaml"]),
            patch("src.selftest.check_module", return_value=0) as mock_check,
        ):
            self.assertEqual(main(), 0)
        mock_check.assert_called_once_with("yaml")


class TestFunctionalChecks(unittest.TestCase):
    def test_vault_roundtrip_passes_with_the_real_provider(self):
        self.assertEqual(check_module("check:vault-roundtrip"), 0)

    def test_vault_roundtrip_detects_a_mismatch(self):
        captured = io.StringIO()
        fake = unittest.mock.MagicMock()
        fake.decrypt.return_value = b"something else"
        with (
            patch("src.providers.ansible.vault.get_vault_lib", return_value=fake),
            contextlib.redirect_stderr(captured),
        ):
            self.assertEqual(check_module("check:vault-roundtrip"), 1)
        self.assertIn("differs", captured.getvalue())

    def test_unknown_functional_check_is_reported(self):
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            self.assertEqual(check_module("check:does-not-exist"), 1)
        self.assertIn("KeyError", captured.getvalue())

    def test_functional_check_is_part_of_every_mode(self):
        with patch.dict("os.environ", {}, clear=False):
            os.environ.pop(_HEADLESS_ENV, None)
            self.assertIn("check:vault-roundtrip", required_checks())
        with patch.dict("os.environ", {_HEADLESS_ENV: "1"}):
            self.assertIn("check:vault-roundtrip", required_checks())


if __name__ == "__main__":
    unittest.main()
