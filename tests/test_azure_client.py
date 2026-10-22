from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch
import unittest

from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

from src.providers.azure import AzureSecretClient
from src.models import SecretItem, SecretVersionItem


class TestAzureSecretClient(unittest.TestCase):
    def setUp(self):
        self.client = AzureSecretClient(vault_name="test-kv")
        self.mock_kv_client = MagicMock()
        self.client._client = self.mock_kv_client

    def test_provider_properties(self):
        self.assertEqual(self.client.provider_id, "azure")
        self.assertEqual(self.client.display_name, "Microsoft Azure (Key Vault)")
        self.assertTrue(self.client.supports_version_toggling)
        self.assertFalse(self.client.supports_version_destroy)
        self.assertEqual(self.client.vault_url, "https://test-kv.vault.azure.net/")
        self.assertIn("test-kv", self.client.context_subtitle)

    @patch.dict("os.environ", {"AZURE_KEYVAULT_NAME": "env-vault"})
    def test_vault_name_detection_from_env(self):
        c = AzureSecretClient()
        self.assertEqual(c.vault_name, "env-vault")
        self.assertEqual(c.vault_url, "https://env-vault.vault.azure.net/")

    def test_list_secrets(self):
        mock_prop = MagicMock()
        mock_prop.id = "https://test-kv.vault.azure.net/secrets/db-pass"
        mock_prop.name = "db-pass"
        mock_prop.content_type = "Database Password"
        mock_prop.created_on = datetime(2026, 1, 1)
        mock_prop.updated_on = datetime(2026, 1, 2)
        mock_prop.tags = {"owner": "devops"}
        mock_prop.enabled = True

        self.mock_kv_client.list_properties_of_secrets.return_value = [mock_prop]

        secrets = self.client.list_secrets()
        self.assertEqual(len(secrets), 1)
        self.assertEqual(secrets[0].secret_id, "db-pass")
        self.assertEqual(secrets[0].labels, {"owner": "devops"})
        self.assertEqual(secrets[0].description, "Database Password")

    def test_list_versions(self):
        v1_prop = MagicMock()
        v1_prop.version = "v1-guid"
        v1_prop.enabled = True
        v1_prop.created_on = datetime(2026, 1, 1)

        v2_prop = MagicMock()
        v2_prop.version = "v2-guid"
        v2_prop.enabled = False
        v2_prop.created_on = datetime(2026, 1, 2)

        self.mock_kv_client.list_properties_of_secret_versions.return_value = [v1_prop, v2_prop]

        versions = self.client.list_versions("db-pass")
        self.assertEqual(len(versions), 2)
        # Sorted by creation date descending: v2 first
        self.assertEqual(versions[0].version_id, "v2-guid")
        self.assertEqual(versions[0].state, "DISABLED")
        self.assertEqual(versions[1].version_id, "v1-guid")
        self.assertEqual(versions[1].state, "ENABLED")

    def test_access_secret_payload(self):
        mock_secret = MagicMock()
        mock_secret.value = "azure-super-secret"
        self.mock_kv_client.get_secret.return_value = mock_secret

        val, is_bin = self.client.access_secret_payload("db-pass@v1-guid")
        self.assertEqual(val, "azure-super-secret")
        self.assertFalse(is_bin)
        self.mock_kv_client.get_secret.assert_called_once_with(name="db-pass", version="v1-guid")

    def test_create_secret(self):
        mock_secret = MagicMock()
        mock_secret.id = "https://test-kv.vault.azure.net/secrets/new-key"
        self.mock_kv_client.set_secret.return_value = mock_secret

        item = self.client.create_secret(
            secret_id="new-key",
            payload_data="api-token-value",
            description="API Token",
            labels={"team": "frontend"},
        )
        self.assertEqual(item.secret_id, "new-key")
        self.mock_kv_client.set_secret.assert_called_once_with(
            name="new-key",
            value="api-token-value",
            tags={"team": "frontend"},
            content_type="API Token",
        )

    def test_add_secret_version(self):
        mock_secret = MagicMock()
        mock_secret.properties.version = "v2-hex"
        self.mock_kv_client.set_secret.return_value = mock_secret

        ver = self.client.add_secret_version("new-key", "updated-payload")
        self.assertEqual(ver.version_id, "v2-hex")
        self.assertEqual(ver.state, "ENABLED")
        self.mock_kv_client.set_secret.assert_called_once_with(name="new-key", value="updated-payload")

    def test_toggle_version_state(self):
        mock_updated = MagicMock()
        mock_updated.version = "v1-hex"
        mock_updated.enabled = False
        mock_updated.created_on = datetime.now()
        self.mock_kv_client.update_secret_properties.return_value = mock_updated

        self.client.toggle_version_state("my-secret@v1-hex", enable=False)
        self.mock_kv_client.update_secret_properties.assert_called_once_with(
            name="my-secret",
            version="v1-hex",
            enabled=False,
        )

    def test_delete_secret(self):
        self.client.delete_secret("old-secret")
        self.mock_kv_client.begin_delete_secret.assert_called_once_with("old-secret")


    def test_additional_properties_and_context_dialog(self):
        self.assertEqual(self.client.provider, "azure")
        self.assertEqual(self.client.icon_name, "security-high-symbolic")
        self.assertIn("Azure", self.client.context_title)
        self.assertIn("Azure", self.client.context_btn_tooltip)
        self.assertIn("Azure", self.client.loading_message)
        self.assertIn("Azure", self.client.empty_message)
        self.assertIn("Azure", self.client.error_message)

        parent = MagicMock()
        on_success = MagicMock()
        with patch("src.ui.dialogs.show_change_azure_vault_dialog") as mock_dialog:
            self.client.open_context_dialog(parent, on_success)
            mock_dialog.assert_called_once()
            on_confirm_cb = mock_dialog.call_args[0][2]
            on_confirm_cb("switched-vault")
            self.assertEqual(self.client.vault_name, "switched-vault")
            on_success.assert_called_once()

    def test_vault_name_and_url_formatting(self):
        c = AzureSecretClient(vault_name="simple-kv")
        self.assertEqual(c.vault_url, "https://simple-kv.vault.azure.net/")

        c.vault_name = "https://custom.vault.azure.net"
        self.assertEqual(c.vault_url, "https://custom.vault.azure.net/")

        c.vault_name = None
        self.assertIsNone(c.vault_url)

    @patch.dict("os.environ", {"AZURE_VAULT_URL": "https://url-detected-kv.vault.azure.net/"})
    def test_detect_vault_name_from_url_env(self):
        self.assertEqual(AzureSecretClient.detect_vault_name(), "url-detected-kv")

    @patch("subprocess.run")
    def test_list_available_vaults_success(self, mock_subproc):
        mock_subproc.return_value = MagicMock(
            returncode=0,
            stdout='[{"name": "kv-prod", "vaultUri": "https://kv-prod.vault.azure.net/", "location": "westeurope"}]',
        )
        vaults = self.client.list_available_vaults()
        self.assertTrue(len(vaults) >= 1)
        names = [v.name for v in vaults]
        self.assertIn("kv-prod", names)
        self.assertIn("test-kv", names)

    @patch("subprocess.run", side_effect=Exception("az cli missing"))
    def test_list_available_vaults_cli_error(self, mock_subproc):
        vaults = self.client.list_available_vaults()
        self.assertEqual(len(vaults), 1)
        self.assertEqual(vaults[0].name, "test-kv")

    def test_get_client_without_vault_raises_value_error(self):
        c = AzureSecretClient(vault_name="dummy")
        c._vault_name = None
        with patch.object(c, "detect_vault_name", return_value=None):
            with self.assertRaises(ValueError):
                c._get_client()

    def test_error_handlers(self):
        from azure.core.exceptions import ClientAuthenticationError, HttpResponseError

        # Auth error
        self.mock_kv_client.list_properties_of_secrets.side_effect = ClientAuthenticationError("Auth failed")
        with self.assertRaises(RuntimeError):
            self.client.list_secrets()

        # Permission error 403 on list secrets
        err_403 = HttpResponseError(message="Forbidden")
        err_403.status_code = 403
        self.mock_kv_client.list_properties_of_secrets.side_effect = err_403
        with self.assertRaises(PermissionError):
            self.client.list_secrets()

        # 404 on list secrets
        err_404 = HttpResponseError(message="Not found")
        err_404.status_code = 404
        self.mock_kv_client.list_properties_of_secrets.side_effect = err_404
        with self.assertRaises(FileNotFoundError):
            self.client.list_secrets()

        # 403 on list versions
        self.mock_kv_client.list_properties_of_secret_versions.side_effect = err_403
        with self.assertRaises(PermissionError):
            self.client.list_versions("sec")

        # 403 on create secret
        self.mock_kv_client.set_secret.side_effect = err_403
        with self.assertRaises(PermissionError):
            self.client.create_secret("sec", "val")

        # 403 on add secret version
        with self.assertRaises(PermissionError):
            self.client.add_secret_version("sec", "val")

        # 403 on access secret payload
        self.mock_kv_client.get_secret.side_effect = err_403
        with self.assertRaises(PermissionError):
            self.client.access_secret_payload("sec")

        # Generic 500 error on methods
        err_500 = HttpResponseError(message="Internal Server Error")
        err_500.status_code = 500

        self.mock_kv_client.list_properties_of_secrets.side_effect = err_500
        with self.assertRaises(RuntimeError):
            self.client.list_secrets()

        self.mock_kv_client.list_properties_of_secret_versions.side_effect = err_500
        with self.assertRaises(RuntimeError):
            self.client.list_versions("sec")

        self.mock_kv_client.get_secret.side_effect = err_500
        with self.assertRaises(RuntimeError):
            self.client.access_secret_payload("sec")

        self.mock_kv_client.set_secret.side_effect = err_500
        with self.assertRaises(RuntimeError):
            self.client.create_secret("sec", "val")

        with self.assertRaises(RuntimeError):
            self.client.add_secret_version("sec", "val")

        # enable/disable version
        mock_prop_enabled = MagicMock(version="v1", enabled=True, created_on=datetime.now())
        self.mock_kv_client.update_secret_properties.return_value = mock_prop_enabled
        v = self.client.enable_secret_version("sec@v1")
        self.assertEqual(v.state, "ENABLED")

        mock_prop_disabled = MagicMock(version="v1", enabled=False, created_on=datetime.now())
        self.mock_kv_client.update_secret_properties.return_value = mock_prop_disabled
        v_dis = self.client.disable_secret_version("sec@v1")
        self.assertEqual(v_dis.state, "DISABLED")

        # enable/disable errors
        self.mock_kv_client.update_secret_properties.side_effect = err_403
        with self.assertRaises(PermissionError):
            self.client.enable_secret_version("sec@v1")

        self.mock_kv_client.update_secret_properties.side_effect = err_500
        with self.assertRaises(RuntimeError):
            self.client.disable_secret_version("sec@v1")

        # delete_secret
        self.mock_kv_client.begin_delete_secret.side_effect = None
        self.client.delete_secret("sec")

        self.mock_kv_client.begin_delete_secret.side_effect = err_403
        with self.assertRaises(PermissionError):
            self.client.delete_secret("sec")

        self.mock_kv_client.begin_delete_secret.side_effect = err_500
        with self.assertRaises(RuntimeError):
            self.client.delete_secret("sec")

    @patch("src.providers.azure.SecretClient")
    @patch("src.providers.azure.DefaultAzureCredential")
    def test_get_client_creates_credential_and_client(self, mock_cred_cls, mock_sc_cls):
        c = AzureSecretClient(vault_name="new-test-vault")
        c._client = None
        c._credential = None
        client_instance = c._get_client()
        mock_cred_cls.assert_called_once()
        mock_sc_cls.assert_called_once()

    def test_azure_client_final_branches(self):
        from azure.core.exceptions import ResourceNotFoundError

        # list_secrets generic exception
        self.mock_kv_client.list_properties_of_secrets.side_effect = TypeError("Unexpected error")
        with self.assertRaises(RuntimeError):
            self.client.list_secrets()

        # access_secret_payload with ResourceNotFoundError
        self.mock_kv_client.get_secret.side_effect = ResourceNotFoundError("Not found")
        with self.assertRaises(FileNotFoundError):
            self.client.access_secret_payload("missing_sec")

        # access_secret_payload with name containing @ and version parameter provided
        self.mock_kv_client.get_secret.side_effect = None
        self.mock_kv_client.get_secret.return_value = MagicMock(value="custom_ver_val")
        val, _ = self.client.access_secret_payload("sec@ver1", version="explicit_ver")
        self.assertEqual(val, "custom_ver_val")
        self.mock_kv_client.get_secret.assert_called_with(name="sec", version="explicit_ver")

        # _set_version_enabled without @ in name
        mock_prop = MagicMock(version="v1", enabled=True, created_on=datetime.now())
        self.mock_kv_client.update_secret_properties.return_value = mock_prop
        self.client.enable_secret_version("sec_without_at")
        self.mock_kv_client.update_secret_properties.assert_called_with(name="sec_without_at", version=None, enabled=True)

        # list_available_vaults with unnamed item and failed cli
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=1, stdout="")
            vaults = self.client.list_available_vaults()
            self.assertEqual(len(vaults), 1)

            mock_sub.return_value = MagicMock(returncode=0, stdout='[{"vaultUri": "https://no-name"}]')
            vaults = self.client.list_available_vaults()
            self.assertEqual(len(vaults), 1)

        # detect_vault_name when az returns empty json
        with patch.dict("os.environ", {}, clear=True):
            with patch("subprocess.run") as mock_sub:
                mock_sub.return_value = MagicMock(returncode=0, stdout="[]")
                self.assertIsNone(AzureSecretClient.detect_vault_name())

    def test_azure_client_100_percent_coverage(self):
        # 1. Branch 103->exit: set vault_name to same value
        self.client.vault_name = "test-kv"
        self.assertEqual(self.client.vault_name, "test-kv")

        # 2. Branch 154->157: list_available_vaults where current vault is already in discovered list
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(
                returncode=0,
                stdout='[{"name": "test-kv", "vaultUri": "https://test-kv.vault.azure.net/", "location": "eastus"}]'
            )
            vaults = self.client.list_available_vaults()
            self.assertEqual(len(vaults), 1)
            self.assertEqual(vaults[0].name, "test-kv")

        # 3. Branch 171->174: _get_client when _credential is not None
        c = AzureSecretClient(vault_name="custom-vault")
        c._credential = MagicMock()
        with patch("src.providers.azure.SecretClient") as mock_sc:
            client_inst = c._get_client()
            self.assertIsNotNone(client_inst)
            mock_sc.assert_called_once()


if __name__ == "__main__":
    unittest.main()

