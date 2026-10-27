from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.providers.ansible.discovery import (
    detect_password_file,
    is_password_file_private,
    read_password_file,
)


class TestPasswordFileHandling(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.temp_dir.name, "pass")
        with open(self.path, "w") as f:
            f.write("s3cret\n")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_password_file_is_not_guessed_from_cwd_or_home(self):
        with open(os.path.join(self.temp_dir.name, ".vault_pass"), "w") as f:
            f.write("x")
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("os.getcwd", return_value=self.temp_dir.name),
            patch("os.path.expanduser", return_value=self.path),
        ):
            self.assertIsNone(detect_password_file())

    def test_explicit_env_var_is_honoured(self):
        with patch.dict("os.environ", {"ANSIBLE_VAULT_PASSWORD_FILE": self.path}):
            self.assertEqual(detect_password_file(), os.path.abspath(self.path))

    @unittest.skipIf(sys.platform == "win32", "POSIX permission bits")
    def test_private_file_is_read(self):
        os.chmod(self.path, 0o600)
        self.assertTrue(is_password_file_private(self.path))
        self.assertEqual(read_password_file(self.path), "s3cret")

    @unittest.skipIf(sys.platform == "win32", "POSIX permission bits")
    def test_group_or_world_accessible_file_is_ignored_with_warning(self):
        for mode in (0o640, 0o604, 0o644):
            os.chmod(self.path, mode)
            captured = io.StringIO()
            with contextlib.redirect_stderr(captured):
                self.assertIsNone(read_password_file(self.path))
            self.assertIn("chmod 600", captured.getvalue())

    def test_missing_file_returns_none(self):
        self.assertIsNone(read_password_file(os.path.join(self.temp_dir.name, "nope")))

    def test_stat_failure_is_treated_as_insecure(self):
        with patch("os.stat", side_effect=OSError("boom")):
            self.assertFalse(is_password_file_private(self.path))

    def test_windows_skips_permission_check(self):
        with patch.object(sys, "platform", "win32"):
            os.chmod(self.path, 0o644)
            self.assertTrue(is_password_file_private(self.path))


if __name__ == "__main__":
    unittest.main()
