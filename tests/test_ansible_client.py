from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.exceptions import ResourceNotFoundError
from src.providers.ansible import AnsibleVaultClient


class TestAnsibleVaultClient(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_file = os.path.join(self.temp_dir.name, "vault.yml")
        self.password = "MyVaultPassword123!"

        # Initialize with an empty file
        with open(self.vault_file, "w") as f:
            f.write("")

        self.client = AnsibleVaultClient(
            vault_file=self.vault_file,
            password=self.password,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_provider_properties(self):
        self.assertEqual(self.client.provider_id, "ansible")
        self.assertEqual(self.client.display_name, "Ansible Vault")
        self.assertFalse(self.client.supports_version_toggling)
        self.assertFalse(self.client.supports_version_destroy)
        self.assertIn("vault.yml", self.client.context_subtitle)

    def test_create_and_list_secrets(self):
        # Create a variable in vault
        self.client.create_secret(
            secret_id="db_password",
            payload_data="s3cr3t_p@ss",
            description="Database Password",
        )

        secrets = self.client.list_secrets()
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0].secret_id, "db_password")
        self.assertEqual(secrets[0].provider, "ansible")

        # Verify that the file on disk was encrypted with Ansible Vault header
        with open(self.vault_file, "rb") as f:
            raw_content = f.read()
        self.assertTrue(raw_content.startswith(b"$ANSIBLE_VAULT"))

    def test_access_secret_payload(self):
        self.client.create_secret(
            secret_id="api_key",
            payload_data="xyz987token",
        )

        val, is_bin = self.client.access_secret_payload("api_key")
        self.assertEqual(val, "xyz987token")
        self.assertFalse(is_bin)

    def test_update_and_delete_secret(self):
        self.client.create_secret(
            secret_id="redis_host",
            payload_data="127.0.0.1",
        )

        # Update (new version)
        self.client.add_secret_version("redis_host", "10.0.0.5")
        val, _ = self.client.access_secret_payload("redis_host")
        self.assertEqual(val, "10.0.0.5")

        # Delete
        self.client.delete_secret("redis_host")
        secrets = self.client.list_secrets()
        self.assertEqual(len(secrets), 0)

    def test_wrong_password_raises_permission_error(self):
        # First save some encrypted secret
        self.client.create_secret(secret_id="test_key", payload_data="val")

        # Create new client with incorrect password pointing to the same encrypted file
        wrong_client = AnsibleVaultClient(
            vault_file=self.vault_file,
            password="WrongPassword!",
        )
        with self.assertRaises(PermissionError):
            wrong_client.list_secrets()

    def test_missing_file_raises_file_not_found(self):
        missing_client = AnsibleVaultClient(
            vault_file=os.path.join(self.temp_dir.name, "nonexistent.yml"),
            password=self.password,
        )
        with self.assertRaises(FileNotFoundError):
            missing_client.list_secrets()

    def test_additional_properties_and_context_dialog(self):
        self.assertEqual(self.client.provider, "ansible")
        self.assertEqual(self.client.icon_name, "document-open-symbolic")
        self.assertIn("Ansible", self.client.context_title)
        self.assertIn("Ansible", self.client.context_btn_tooltip)
        self.assertIn("Ansible", self.client.loading_message)
        self.assertIn("Ansible", self.client.empty_message)
        self.assertIn("Ansible", self.client.error_message)

        # Setters
        self.client.vault_id = "custom_id"
        self.assertEqual(self.client.vault_id, "custom_id")
        self.client.password = "new_pass"
        self.assertEqual(self.client.password, "new_pass")

        # Context dialog
        parent = MagicMock()
        on_success = MagicMock()
        with patch("src.ui.dialogs.show_change_ansible_vault_dialog") as mock_dialog:
            self.client.open_context_dialog(parent, on_success)
            mock_dialog.assert_called_once()
            on_confirm_cb = mock_dialog.call_args[0][2]
            on_confirm_cb(self.vault_file, "p123", None)
            self.assertEqual(self.client.password, "p123")
            on_success.assert_called_once()

    def test_backup_version_history_and_access(self):
        self.client.create_secret(secret_id="versioned_key", payload_data="version_1")
        # Update creates backup
        self.client.add_secret_version("versioned_key", "version_2")

        versions = self.client.list_versions("versioned_key")
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].version_id, "1")
        self.assertEqual(versions[1].version_id, "0")

        # Fetch backup version
        old_val, _ = self.client.access_secret_payload("versioned_key", version="backup")
        self.assertEqual(old_val, "version_1")

        curr_val, _ = self.client.access_secret_payload("versioned_key")
        self.assertEqual(curr_val, "version_2")

    def test_create_complex_dict_payload(self):
        self.client.create_secret(
            secret_id="database_config",
            payload_data="host: 127.0.0.1\nport: 5432\nuser: postgres",
        )
        val, _ = self.client.access_secret_payload("database_config")
        self.assertIn("host", val)
        self.assertIn("5432", val)

    def test_create_secret_already_exists(self):
        self.client.create_secret(secret_id="dup_key", payload_data="val1")
        with self.assertRaises(ValueError):
            self.client.create_secret(secret_id="dup_key", payload_data="val2")

    def test_detection_methods(self):
        # Env vault file
        with patch.dict("os.environ", {"ANSIBLE_VAULT_FILE": self.vault_file}):
            self.assertEqual(
                AnsibleVaultClient.detect_vault_file(), os.path.abspath(self.vault_file)
            )

        # The password is never read from the environment
        with patch.dict("os.environ", {"ANSIBLE_VAULT_PASSWORD": "env_password"}, clear=True):
            self.assertIsNone(AnsibleVaultClient.detect_password())

        # Password file detection
        pass_file_path = os.path.join(self.temp_dir.name, ".vault_pass")
        with open(pass_file_path, "w") as f:
            f.write("file_secret_pass\n")

        with patch.dict("os.environ", {"ANSIBLE_VAULT_PASSWORD_FILE": pass_file_path}):
            self.assertEqual(
                AnsibleVaultClient.detect_password_file(), os.path.abspath(pass_file_path)
            )

        # Find local vault files
        with patch("os.getcwd", return_value=self.temp_dir.name):
            vaults = AnsibleVaultClient.find_local_vault_files()
            self.assertIn(os.path.abspath(self.vault_file), [os.path.abspath(v) for v in vaults])

    def test_unlock_helper(self):
        self.assertTrue(self.client.unlock(password=self.password))
        self.assertTrue(self.client.is_unlocked)

    def test_create_new_vault_file(self):
        new_file = os.path.join(self.temp_dir.name, "new_vault.yml")
        self.client.create_new_vault_file(new_file, "NewPass123!", {"key1": "val1"})
        self.assertEqual(self.client.vault_file, os.path.abspath(new_file))
        val, _ = self.client.access_secret_payload("key1")
        self.assertEqual(val, "val1")

    def test_parse_payload_variations(self):
        # JSON / Dict
        self.client.create_secret(secret_id="dict_var", payload_data='{"a": 1, "b": "hello"}')
        val, _ = self.client.access_secret_payload("dict_var")
        self.assertIn("a: 1", val)

        # List
        self.client.create_secret(secret_id="list_var", payload_data="[1, 2, 3]")
        val, _ = self.client.access_secret_payload("list_var")
        self.assertIn("- 1", val)

        # Booleans
        self.client.create_secret(secret_id="bool_var", payload_data="true")
        val, _ = self.client.access_secret_payload("bool_var")
        self.assertEqual(val, "True")

    def test_password_file_usage(self):
        pass_file = os.path.join(self.temp_dir.name, "passfile.txt")
        with open(pass_file, "w") as f:
            f.write("SecretPassFromFile\n")

        self.client.password = None
        self.client.password_file = pass_file
        self.assertEqual(self.client.password_file, os.path.abspath(pass_file))

        # Re-encrypt file with new password
        self.client.create_new_vault_file(self.vault_file, "SecretPassFromFile", {"foo": "bar"})
        # Now access secret using password_file
        val, _ = self.client.access_secret_payload("foo")
        self.assertEqual(val, "bar")

    def test_access_secret_payload_key_error(self):
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload("nonexistent_key_123")

    def test_no_password_raises_permission_error(self):
        self.client.password = None
        self.client.password_file = None
        with self.assertRaises(PermissionError):
            self.client._get_vault_lib()

    def test_save_data_missing_vault_file_raises_value_error(self):
        self.client.vault_file = None
        with self.assertRaises(ValueError):
            self.client._save_data({"test": 123})

    def test_invalid_yaml_decrypted_raises_runtime_error(self):
        # Save a file with invalid YAML
        from ansible.constants import DEFAULT_VAULT_ID_MATCH
        from ansible.parsing.vault import VaultLib, VaultSecret

        vault_lib = VaultLib([(DEFAULT_VAULT_ID_MATCH, VaultSecret(self.password.encode("utf-8")))])
        encrypted = vault_lib.encrypt(b": this is : not : valid: yaml: [")
        with open(self.vault_file, "wb") as f:
            f.write(encrypted)

        self.client._invalidate_cache()
        with self.assertRaises(RuntimeError):
            self.client._load_data()

    def test_unlock_with_all_parameters(self):
        self.assertTrue(
            self.client.unlock(
                vault_file=self.vault_file,
                password=self.password,
                password_file=None,
                vault_id="custom_vault",
            )
        )
        self.assertEqual(self.client.vault_id, "custom_vault")

    def test_load_data_scalar_wrapped(self):
        # Save vault containing a plain string scalar instead of a dict
        from ansible.constants import DEFAULT_VAULT_ID_MATCH
        from ansible.parsing.vault import VaultLib, VaultSecret

        vault_lib = VaultLib([(DEFAULT_VAULT_ID_MATCH, VaultSecret(self.password.encode("utf-8")))])
        encrypted = vault_lib.encrypt(b"just a plain scalar string")
        with open(self.vault_file, "wb") as f:
            f.write(encrypted)

        self.client._invalidate_cache()
        data = self.client._load_data()
        self.assertIn("content", data)
        self.assertEqual(data["content"], "just a plain scalar string")

    def test_detect_password_from_file_fallback(self):
        pass_file_path = os.path.join(self.temp_dir.name, ".vault_pass")
        with open(pass_file_path, "w") as f:
            f.write("fallback_pass\n")
        os.chmod(pass_file_path, 0o600)

        with patch.dict("os.environ", {}, clear=True):
            with patch.object(
                AnsibleVaultClient, "detect_password_file", return_value=pass_file_path
            ):
                pwd = AnsibleVaultClient.detect_password()
                self.assertEqual(pwd, "fallback_pass")

    def test_context_dialog_with_pass_file_callback(self):
        parent = MagicMock()
        on_success = MagicMock()
        with patch("src.ui.dialogs.show_change_ansible_vault_dialog") as mock_dialog:
            self.client.open_context_dialog(parent, on_success)
            on_confirm_cb = mock_dialog.call_args[0][2]
            on_confirm_cb(self.vault_file, None, "/path/to/pass")
            self.assertEqual(self.client.password_file, os.path.abspath("/path/to/pass"))
            on_success.assert_called_once()

    def test_properties_detection_fallbacks(self):
        c = AnsibleVaultClient()
        c._password = None
        c._password_file = None
        with (
            patch.object(c, "detect_password", return_value="detected_p"),
            patch.object(c, "detect_password_file", return_value="/detected/file"),
        ):
            self.assertEqual(c.password, "detected_p")
            self.assertEqual(c.password_file, "/detected/file")

    def test_delete_nonexistent_secret(self):
        self.client.delete_secret("never_existed_variable")

    def test_parse_payload_malformed_json_fallback(self):
        val = self.client._parse_payload("{this is: not valid json")
        self.assertEqual(val, "{this is: not valid json")

    def test_load_data_empty_yaml(self):
        from ansible.constants import DEFAULT_VAULT_ID_MATCH
        from ansible.parsing.vault import VaultLib, VaultSecret

        vault_lib = VaultLib([(DEFAULT_VAULT_ID_MATCH, VaultSecret(self.password.encode("utf-8")))])
        encrypted = vault_lib.encrypt(b"")
        with open(self.vault_file, "wb") as f:
            f.write(encrypted)
        self.client._invalidate_cache()
        self.assertEqual(self.client._load_data(), {})

    def test_access_secret_backup_without_backup_file_raises(self):
        bak = f"{self.vault_file}.bak"
        if os.path.exists(bak):
            os.remove(bak)
        self.client.create_secret(secret_id="no_bak", payload_data="val")
        if os.path.exists(bak):
            os.remove(bak)
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload("no_bak", version="backup")

    def test_ansible_client_100_percent_coverage(self):
        # 1. detect_vault_file candidate (176)
        with patch("os.path.exists", side_effect=lambda p: p.endswith(".vault.yml")):
            found = AnsibleVaultClient.detect_vault_file()
            self.assertIsNotNone(found)
            self.assertTrue(found.endswith(".vault.yml"))

        # 2. password files are never guessed from the workspace or home folder
        with patch.dict("os.environ", {}, clear=True):
            with patch("os.path.exists", return_value=True):
                self.assertIsNone(AnsibleVaultClient.detect_password_file())

        # 3. detect_password exception on read
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(
                AnsibleVaultClient, "detect_password_file", return_value="/some/pass"
            ):
                with patch("os.path.exists", return_value=True):
                    with patch(
                        "src.providers.ansible.discovery.is_password_file_private",
                        return_value=True,
                    ):
                        with patch("builtins.open", side_effect=PermissionError("Denied")):
                            self.assertIsNone(AnsibleVaultClient.detect_password())

        # 4. find_local_vault_files branches and exceptions (230, 231->223, 233-236)
        with patch("os.walk") as mock_walk:
            mock_walk.return_value = [
                ("/project", ["subdir"], ["plain.yml", "corrupted.yml", "vault_secret.yml"]),
            ]

            def fake_open(path, mode="r", **kwargs):
                if "corrupted.yml" in path:
                    raise IOError("Read error")
                elif "plain.yml" in path:
                    return unittest.mock.mock_open(read_data=b"not_vault: true")()
                elif "vault_secret.yml" in path:
                    return unittest.mock.mock_open(read_data=b"$ANSIBLE_VAULT;1.1;AES256")()
                return unittest.mock.mock_open(read_data=b"")()

            with patch("builtins.open", side_effect=fake_open):
                found = AnsibleVaultClient.find_local_vault_files()
                self.assertIn("/project/vault_secret.yml", found)

        with patch("os.walk", side_effect=Exception("Walk failure")):
            self.assertEqual(AnsibleVaultClient.find_local_vault_files(), [])

        # 5. _get_active_password with password_file success and exception (243-247)
        c = AnsibleVaultClient(vault_file=self.vault_file, password=None)
        c._password = None
        c._password_file = "/fake/pass"
        with (
            patch("os.path.exists", return_value=True),
            patch("src.providers.ansible.discovery.is_password_file_private", return_value=True),
        ):
            with patch("builtins.open", unittest.mock.mock_open(read_data="file_pass\n")):
                self.assertEqual(c._get_active_password(), "file_pass")
            with patch("builtins.open", side_effect=Exception("IO")):
                self.assertIsNone(c._get_active_password())

        # 6. unlock with password=None and password_file set (271->273, 274)
        c.unlock(vault_file=self.vault_file, password=None, password_file="/new/pass")
        self.assertEqual(c._password_file, "/new/pass")

        # 7. _load_data without vault_file (287)
        c.vault_file = None
        c._vault_file = None
        with patch.object(c, "detect_vault_file", return_value=None):
            with self.assertRaises(FileNotFoundError):
                c._load_data()

        # 8. _load_data unencrypted YAML file and dict parsing (323-324, 330->336)
        plain_file = os.path.join(self.temp_dir.name, "plain_unencrypted.yml")
        with open(plain_file, "w", encoding="utf-8") as f:
            f.write("user: admin\nport: 8080\n")
        c_plain = AnsibleVaultClient(vault_file=plain_file, password="any")
        data = c_plain._load_data()
        self.assertEqual(data["user"], "admin")

        # 9. _load_data with generic decrypt exception (319-321)
        with open(plain_file, "wb") as f:
            f.write(b"$ANSIBLE_VAULT;1.1;AES256\n1234")
        c_plain._invalidate_cache()
        with patch.object(c_plain, "_get_vault_lib") as mock_lib:
            mock_lib.return_value.decrypt.side_effect = TypeError("Corrupted header")
            with self.assertRaises(RuntimeError):
                c_plain._load_data()

        # 10. _save_data backup copy exception (355-356)
        with patch("shutil.copy2", side_effect=Exception("Backup permission denied")):
            with self.assertRaises(RuntimeError):
                self.client.create_secret("sec_with_bak_err", "val")
        self.client.create_secret("sec_with_bak_err", "val")

        # 11. list_versions without backup file (425->441) and backup getmtime exception (438-439)
        bak_file = f"{self.vault_file}.bak"
        if os.path.exists(bak_file):
            os.remove(bak_file)
        vers = self.client.list_versions("sec_with_bak_err")
        self.assertEqual(len(vers), 1)

        # with backup file where getmtime fails (438-439)
        with open(bak_file, "w") as f:
            f.write("bak")

        def fake_getmtime(p):
            if str(p).endswith(".bak"):
                raise OSError("Mtime fail")
            return 123456789.0

        with patch("os.path.getmtime", side_effect=fake_getmtime):
            vers2 = self.client.list_versions("sec_with_bak_err")
            self.assertEqual(len(vers2), 1)

        # 12. access_secret_payload backup branches (457->465, 460, 462-463)
        # Create a valid encrypted backup file with dict payload
        self.client.create_secret("dict_key", '{"nested": {"a": 1}}')
        self.client.add_secret_version("dict_key", '{"nested": {"a": 2}}')
        # dict_key in backup has dict value (460)
        val, _ = self.client.access_secret_payload("dict_key", version="backup")
        self.assertIn("nested", val)

        # key missing in backup data (457->465)
        self.client.create_secret("new_only_key", "val_only_new")
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload("new_only_key", version="backup")

        # exception decrypting backup file (462-463)
        with patch.object(self.client, "_get_vault_lib") as mock_lib:
            mock_lib.return_value.decrypt.side_effect = Exception("Backup decrypt broken")
            with self.assertRaises(RuntimeError):
                self.client.access_secret_payload("dict_key", version="backup")


class TestVersionedPayloadNames(unittest.TestCase):
    """The GUI reads values with the '<variable>@<version>' names returned by list_versions."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_file = os.path.join(self.temp_dir.name, "vault.yml")
        self.client = AnsibleVaultClient(vault_file=self.vault_file, password="pw")
        self.client.create_new_vault_file(self.vault_file, "pw")
        self.client.create_secret("api", "first")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_current_version_name_returns_the_value(self):
        versions = self.client.list_versions("api")
        self.assertEqual(versions[0].name, "api@1")
        self.assertEqual(self.client.access_secret_payload(versions[0].name), ("first", False))

    def test_backup_version_name_returns_the_previous_value(self):
        self.client.add_secret_version("api", "second")
        names = [v.name for v in self.client.list_versions("api")]
        self.assertIn("api@backup", names)
        self.assertEqual(self.client.access_secret_payload("api@backup")[0], "first")
        self.assertEqual(self.client.access_secret_payload("api@1")[0], "second")

    def test_full_resource_name_with_version_suffix(self):
        name = f"{self.vault_file}::api@1"
        self.assertEqual(self.client.access_secret_payload(name)[0], "first")

    def test_explicit_version_wins_over_suffix(self):
        self.client.add_secret_version("api", "second")
        self.assertEqual(self.client.access_secret_payload("api@1", version="backup")[0], "first")

    def test_variable_names_containing_at_still_work(self):
        self.client.create_secret("user@host", "ssh")
        self.assertEqual(self.client.access_secret_payload("user@host")[0], "ssh")
        self.assertEqual(self.client.access_secret_payload("user@host@1")[0], "ssh")

    def test_unknown_variable_still_raises(self):
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload("missing@1")


class TestVaultLock(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.vault_file = os.path.join(self.temp_dir.name, "vault.yml")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lock_forgets_typed_password_and_decrypted_contents(self):
        client = AnsibleVaultClient(vault_file=self.vault_file, password="pw")
        client.create_new_vault_file(self.vault_file, "pw")
        client.create_secret("api", "value")
        self.assertTrue(client.is_unlocked)

        client.lock()

        self.assertFalse(client.is_unlocked)
        self.assertIsNone(client._password)
        self.assertIsNone(client._cached_dict)
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(PermissionError):
                client.list_secrets()

    def test_lock_with_password_file_unlocks_again_from_the_private_file(self):
        pass_file = os.path.join(self.temp_dir.name, "pass")
        with open(pass_file, "w") as handle:
            handle.write("pw\n")
        os.chmod(pass_file, 0o600)
        client = AnsibleVaultClient(
            vault_file=self.vault_file, password="pw", password_file=pass_file
        )
        client.create_new_vault_file(self.vault_file, "pw")
        client.create_secret("api", "value")

        client.lock()

        self.assertFalse(client.is_unlocked)
        self.assertEqual([s.secret_id for s in client.list_secrets()], ["api"])
        self.assertTrue(client.is_unlocked)

    def test_base_provider_lock_is_a_noop(self):
        from src.providers import GCPSecretClient

        self.assertIsNone(GCPSecretClient().lock())


if __name__ == "__main__":
    unittest.main()
