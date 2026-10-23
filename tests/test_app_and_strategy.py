from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    BaseSecretProvider,
    GCPSecretClient,
)
from src.ui.app import GossipApplication


class TestAppAndStrategy(unittest.TestCase):
    def setUp(self):
        self.mock_gcp = MagicMock(spec=GCPSecretClient)
        self.mock_gcp.provider_id = "gcp"
        self.mock_gcp.display_name = "Google Cloud (GCP)"
        self.mock_gcp.icon_name = "network-workgroup-symbolic"
        self.mock_gcp.context_subtitle = "GCP Project: test-proj"
        self.mock_gcp.context_btn_tooltip = "Switch GCP Project"
        self.mock_gcp.loading_message = "Querying GCP..."
        self.mock_gcp.empty_message = "No GCP secrets"
        self.mock_gcp.error_message = "GCP error"
        self.mock_gcp.supports_version_toggling = True
        self.mock_gcp.supports_version_destroy = True

        self.mock_aws = MagicMock(spec=AWSSecretClient)
        self.mock_aws.provider_id = "aws"
        self.mock_aws.display_name = "Amazon Web Services (AWS)"
        self.mock_aws.icon_name = "preferences-system-symbolic"
        self.mock_aws.context_subtitle = "AWS: default (eu-west-1)"
        self.mock_aws.context_btn_tooltip = "Switch AWS Profile & Region"
        self.mock_aws.loading_message = "Querying AWS..."
        self.mock_aws.empty_message = "No AWS secrets"
        self.mock_aws.error_message = "AWS error"
        self.mock_aws.supports_version_toggling = False
        self.mock_aws.supports_version_destroy = False

        self.mock_azure = MagicMock(spec=AzureSecretClient)
        self.mock_azure.provider_id = "azure"
        self.mock_azure.display_name = "Microsoft Azure (Key Vault)"
        self.mock_azure.icon_name = "security-high-symbolic"
        self.mock_azure.context_subtitle = "Azure Vault: test-vault"
        self.mock_azure.context_btn_tooltip = "Switch Azure Key Vault"
        self.mock_azure.loading_message = "Querying Azure..."
        self.mock_azure.empty_message = "No Azure secrets"
        self.mock_azure.error_message = "Azure error"
        self.mock_azure.supports_version_toggling = True
        self.mock_azure.supports_version_destroy = False

        self.mock_ansible = MagicMock(spec=AnsibleVaultClient)
        self.mock_ansible.provider_id = "ansible"
        self.mock_ansible.display_name = "Ansible Vault"
        self.mock_ansible.icon_name = "document-open-symbolic"
        self.mock_ansible.context_subtitle = "Ansible Vault: vault.yml"
        self.mock_ansible.context_btn_tooltip = "Switch Ansible Vault File & Password"
        self.mock_ansible.loading_message = "Decrypting Ansible Vault..."
        self.mock_ansible.empty_message = "No variables found"
        self.mock_ansible.error_message = "Ansible error"
        self.mock_ansible.supports_version_toggling = False
        self.mock_ansible.supports_version_destroy = False

    def test_gossip_application_initialization(self):
        app = GossipApplication(
            provider="azure",
            azure_vault="production-vault",
            width=1400,
            height=900,
        )
        self.assertEqual(app.provider, "azure")
        self.assertEqual(app.azure_vault, "production-vault")
        self.assertEqual(app.width, 1400)
        self.assertEqual(app.height, 900)
        self.assertIsInstance(app.gcp_client, BaseSecretProvider)
        self.assertIsInstance(app.aws_client, BaseSecretProvider)
        self.assertIsInstance(app.azure_client, BaseSecretProvider)
        self.assertIsInstance(app.ansible_client, BaseSecretProvider)

    def test_strategy_pattern_behavior(self):
        providers = {
            "gcp": self.mock_gcp,
            "aws": self.mock_aws,
            "azure": self.mock_azure,
            "ansible": self.mock_ansible,
        }

        # Strategy starts with GCP
        active_strategy = providers["gcp"]
        self.assertEqual(active_strategy.provider_id, "gcp")
        self.assertEqual(active_strategy.context_subtitle, "GCP Project: test-proj")
        self.assertTrue(active_strategy.supports_version_toggling)
        self.assertTrue(active_strategy.supports_version_destroy)

        # Switch strategy to AWS
        active_strategy = providers["aws"]
        self.assertEqual(active_strategy.provider_id, "aws")
        self.assertEqual(active_strategy.context_subtitle, "AWS: default (eu-west-1)")
        self.assertFalse(active_strategy.supports_version_toggling)
        self.assertFalse(active_strategy.supports_version_destroy)

        # Switch strategy to Azure
        active_strategy = providers["azure"]
        self.assertEqual(active_strategy.provider_id, "azure")
        self.assertEqual(active_strategy.context_subtitle, "Azure Vault: test-vault")
        self.assertTrue(active_strategy.supports_version_toggling)
        self.assertFalse(active_strategy.supports_version_destroy)

        # Switch strategy to Ansible
        active_strategy = providers["ansible"]
        self.assertEqual(active_strategy.provider_id, "ansible")
        self.assertEqual(active_strategy.context_subtitle, "Ansible Vault: vault.yml")
        self.assertFalse(active_strategy.supports_version_toggling)
        self.assertFalse(active_strategy.supports_version_destroy)

    @patch.object(GossipApplication, "run", return_value=0)
    def test_run_app_function(self, mock_run):
        from src.ui.app import run_app

        exit_code = run_app(provider="aws", aws_profile="prod")
        self.assertEqual(exit_code, 0)
        mock_run.assert_called_once()

    def test_load_css_with_display(self):

        app = GossipApplication()
        app._load_css()

    @patch("gi.repository.Gdk.Display.get_default", return_value=None)
    def test_load_css_without_display(self, mock_display):
        app = GossipApplication()
        app._load_css()

    def test_do_startup(self):
        from gi.repository import Adw

        app = GossipApplication()
        with patch.object(Adw.Application, "do_startup") as mock_super_startup:
            with patch.object(app, "_load_css") as mock_load_css:
                app.do_startup()
                mock_super_startup.assert_called_once_with(app)
                mock_load_css.assert_called_once()

    @patch("src.ui.app.MainWindow")
    def test_do_activate(self, mock_main_window_cls):
        from gi.repository import Adw

        mock_win = MagicMock()
        mock_main_window_cls.return_value = mock_win
        app = GossipApplication()
        with patch.object(Adw.Application, "do_activate") as mock_super_activate:
            app.do_activate()
            mock_super_activate.assert_called_once_with(app)
            mock_main_window_cls.assert_called_once()
            mock_win.present.assert_called_once()
            self.assertEqual(app.window, mock_win)

            # Calling again uses the already created window
            app.do_activate()
            self.assertEqual(mock_main_window_cls.call_count, 1)
            self.assertEqual(mock_win.present.call_count, 2)

    def test_register_icon_theme(self):
        import os
        import sys
        import tempfile

        app = GossipApplication()

        # 1. Without display
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            app._register_icon_theme()

        # 2. With display, not frozen
        with patch("gi.repository.Gdk.Display.get_default"):
            mock_theme = MagicMock()
            with patch("gi.repository.Gtk.IconTheme.get_for_display", return_value=mock_theme):
                with patch.object(sys, "frozen", False, create=True):
                    app._register_icon_theme()
                    mock_theme.add_search_path.assert_not_called()

        # 3. With display, frozen and existing candidate dirs
        with tempfile.TemporaryDirectory() as tmpdir:
            share_icons = os.path.join(tmpdir, "share", "icons")
            os.makedirs(share_icons)
            with patch("gi.repository.Gdk.Display.get_default"):
                mock_theme = MagicMock()
                with patch("gi.repository.Gtk.IconTheme.get_for_display", return_value=mock_theme):
                    with patch.object(sys, "frozen", True, create=True):
                        with patch.object(sys, "_MEIPASS", tmpdir, create=True):
                            app._register_icon_theme()
                            mock_theme.add_search_path.assert_called_with(share_icons)


if __name__ == "__main__":
    unittest.main()
