from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.providers.ansible.vault import load_vault_data, save_vault_data

PASSWORD = "MyVaultPassword123!"


class TestVaultSaveSafety(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_file = os.path.join(self.temp_dir.name, "vault.yml")

    def tearDown(self):
        self.temp_dir.cleanup()

    @unittest.skipIf(sys.platform == "win32", "POSIX permission bits")
    def test_new_vault_is_owner_only(self):
        save_vault_data(self.vault_file, {"a": "1"}, PASSWORD)
        self.assertEqual(stat.S_IMODE(os.stat(self.vault_file).st_mode), 0o600)

    @unittest.skipIf(sys.platform == "win32", "POSIX permission bits")
    def test_existing_permissions_are_preserved(self):
        save_vault_data(self.vault_file, {"a": "1"}, PASSWORD)
        os.chmod(self.vault_file, 0o640)
        save_vault_data(self.vault_file, {"a": "2"}, PASSWORD)
        self.assertEqual(stat.S_IMODE(os.stat(self.vault_file).st_mode), 0o640)
        self.assertEqual(load_vault_data(self.vault_file, PASSWORD), {"a": "2"})

    def test_backup_failure_aborts_save_and_keeps_original(self):
        save_vault_data(self.vault_file, {"a": "1"}, PASSWORD)
        with patch("shutil.copy2", side_effect=OSError("disk full")):
            with self.assertRaises(RuntimeError):
                save_vault_data(self.vault_file, {"a": "2"}, PASSWORD)
        self.assertEqual(load_vault_data(self.vault_file, PASSWORD), {"a": "1"})


class TestYamlErrorDoesNotLeak(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_file = os.path.join(self.temp_dir.name, "plain.yml")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_error_reports_position_not_content(self):
        with open(self.vault_file, "w") as f:
            f.write("ok: 1\ntoken: [unclosed hunter2-super-secret\n")
        with self.assertRaises(RuntimeError) as ctx:
            load_vault_data(self.vault_file, None)
        message = str(ctx.exception)
        self.assertNotIn("hunter2-super-secret", message)
        self.assertIn("line", message)

    def test_error_without_position_reports_class_name(self):
        with open(self.vault_file, "w") as f:
            f.write("a: 1\n")
        with patch("yaml.safe_load", side_effect=ValueError("secret-in-message")):
            with self.assertRaises(RuntimeError) as ctx:
                load_vault_data(self.vault_file, None)
        self.assertNotIn("secret-in-message", str(ctx.exception))
        self.assertIn("ValueError", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
