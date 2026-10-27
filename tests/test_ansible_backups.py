from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.exceptions import ResourceNotFoundError
from src.providers.ansible import AnsibleVaultClient
from src.providers.ansible.vault import (
    BACKUP_GENERATIONS,
    backup_path,
    list_backup_generations,
    save_vault_data,
)


class TestBackupRotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = os.path.join(self.tmp.name, "vault.yml")

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_paths(self):
        self.assertEqual(backup_path(self.vault), f"{self.vault}.bak")
        self.assertEqual(backup_path(self.vault, 1), f"{self.vault}.bak")
        self.assertEqual(backup_path(self.vault, 3), f"{self.vault}.bak.3")

    def test_each_save_pushes_older_states_back_and_keeps_a_fixed_number(self):
        client = AnsibleVaultClient(vault_file=self.vault, password="pw")
        client.create_new_vault_file(self.vault, "pw")  # save 1: no backup yet
        self.assertEqual(list_backup_generations(self.vault), [])

        for number in range(1, 9):
            data = client._load_data()
            data["counter"] = number
            client._save_data(data)

        self.assertEqual(
            list_backup_generations(self.vault), list(range(1, BACKUP_GENERATIONS + 1))
        )
        self.assertFalse(os.path.exists(backup_path(self.vault, BACKUP_GENERATIONS + 1)))

        # generation 1 holds the state before the last save, 2 the one before, ...
        for generation in range(1, BACKUP_GENERATIONS + 1):
            value, _binary = client.access_secret_payload(
                "counter", version="backup" if generation == 1 else f"backup{generation}"
            )
            self.assertEqual(value, str(8 - generation))

    def test_versions_list_names_every_generation(self):
        client = AnsibleVaultClient(vault_file=self.vault, password="pw")
        client.create_new_vault_file(self.vault, "pw")
        client.create_secret("k", "v1")
        for text in ("v2", "v3", "v4"):
            client.add_secret_version("k", text)

        versions = client.list_versions("k")
        # the oldest backup predates the variable, so it is not offered as a version
        self.assertEqual([v.name for v in versions], ["k@1", "k@backup", "k@backup2", "k@backup3"])
        self.assertEqual([v.version_id for v in versions], ["1", "0", "-1", "-2"])
        self.assertEqual(versions[1].stages, ["AWSPREVIOUS"])
        self.assertIn("2", versions[2].stages[0])
        self.assertTrue(all(v.create_time is not None for v in versions))

        values = [client.access_secret_payload(v.name)[0] for v in versions]
        self.assertEqual(values, ["v4", "v3", "v2", "v1"])

    def test_variable_missing_in_an_old_backup_is_reported_not_substituted(self):
        client = AnsibleVaultClient(vault_file=self.vault, password="pw")
        client.create_new_vault_file(self.vault, "pw")
        client.create_secret("old", "x")
        client.create_secret("new", "y")  # the backup taken before this save lacks "new"
        with self.assertRaises(ResourceNotFoundError):
            client.access_secret_payload("new@backup")
        self.assertEqual(client.access_secret_payload("old@backup")[0], "x")

    def test_unknown_generation_is_reported(self):
        client = AnsibleVaultClient(vault_file=self.vault, password="pw")
        client.create_new_vault_file(self.vault, "pw")
        client.create_secret("k", "v")
        with self.assertRaises(ResourceNotFoundError):
            client.access_secret_payload("k@backup5")

    def test_rotation_failure_aborts_the_save_and_keeps_the_original(self):
        client = AnsibleVaultClient(vault_file=self.vault, password="pw")
        client.create_new_vault_file(self.vault, "pw")
        client.create_secret("k", "original")
        with patch("os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(RuntimeError):
                save_vault_data(self.vault, {"k": "changed"}, "pw")
        client._invalidate_cache()
        self.assertEqual(client.access_secret_payload("k")[0], "original")

    @unittest.skipIf(sys.platform == "win32", "POSIX permission bits")
    def test_backups_keep_the_vault_permissions(self):
        client = AnsibleVaultClient(vault_file=self.vault, password="pw")
        client.create_new_vault_file(self.vault, "pw")
        os.chmod(self.vault, 0o640)
        for number in range(3):
            data = client._load_data()
            data["n"] = number
            client._save_data(data)
        for generation in list_backup_generations(self.vault):
            mode = stat.S_IMODE(os.stat(backup_path(self.vault, generation)).st_mode)
            self.assertEqual(mode, 0o640)


if __name__ == "__main__":
    unittest.main()
