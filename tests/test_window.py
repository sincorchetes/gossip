from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from src.models import SecretItem, SecretVersionItem
from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    GCPSecretClient,
    KubernetesClient,
    SSMClient,
    VaultClient,
)
from src.ui.window import MainWindow


class DummySyncThread:
    def __init__(self, target, *args, **kwargs):
        self.target = target

    def start(self):
        self.target()


class TestMainWindow(unittest.TestCase):
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
        self.mock_gcp.project_id = "test-proj"
        self.mock_gcp.list_secrets.return_value = []

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
        self.mock_aws.list_secrets.return_value = []

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
        self.mock_azure.list_secrets.return_value = []

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
        self.mock_ansible.is_unlocked = True
        self.mock_ansible.list_secrets.return_value = []

        self.mock_k8s = MagicMock(spec=KubernetesClient)
        self.mock_k8s.provider_id = "k8s"
        self.mock_k8s.display_name = "Kubernetes Secrets"
        self.mock_k8s.icon_name = "network-server-symbolic"
        self.mock_k8s.context_subtitle = "Kubernetes: dev"
        self.mock_k8s.context_btn_tooltip = "Switch context"
        self.mock_k8s.loading_message = "Querying..."
        self.mock_k8s.empty_message = "No secrets"
        self.mock_k8s.error_message = "K8s error"
        self.mock_k8s.supports_version_toggling = False
        self.mock_k8s.supports_version_destroy = False
        self.mock_k8s.list_secrets.return_value = []

        self.mock_ssm = MagicMock(spec=SSMClient)
        self.mock_ssm.provider_id = "ssm"
        self.mock_ssm.display_name = "AWS Parameter Store"
        self.mock_ssm.icon_name = "preferences-system-symbolic"
        self.mock_ssm.context_subtitle = "Parameter Store: dev"
        self.mock_ssm.context_btn_tooltip = "Switch AWS Profile"
        self.mock_ssm.loading_message = "Querying..."
        self.mock_ssm.empty_message = "No parameters"
        self.mock_ssm.error_message = "AWS error"
        self.mock_ssm.supports_version_toggling = False
        self.mock_ssm.supports_version_destroy = False
        self.mock_ssm.list_secrets.return_value = []

        self.mock_vault = MagicMock(spec=VaultClient)
        self.mock_vault.provider_id = "vault"
        self.mock_vault.display_name = "HashiCorp Vault / OpenBao"
        self.mock_vault.icon_name = "security-high-symbolic"
        self.mock_vault.context_subtitle = "Vault: test"
        self.mock_vault.context_btn_tooltip = "Change Vault server"
        self.mock_vault.loading_message = "Querying Vault..."
        self.mock_vault.empty_message = "No Vault secrets"
        self.mock_vault.error_message = "Vault error"
        self.mock_vault.supports_version_toggling = True
        self.mock_vault.supports_version_destroy = True
        self.mock_vault.list_secrets.return_value = []

        self.window = MainWindow(
            provider="gcp",
            gcp_client=self.mock_gcp,
            aws_client=self.mock_aws,
            azure_client=self.mock_azure,
            ansible_client=self.mock_ansible,
            vault_client=self.mock_vault,
            ssm_client=self.mock_ssm,
            k8s_client=self.mock_k8s,
        )

    def test_window_initial_state(self):
        self.assertEqual(self.window.current_provider, "gcp")
        self.assertEqual(self.window.active_provider, self.mock_gcp)
        self.assertEqual(self.window.client, self.mock_gcp)

    def test_provider_switching(self):
        # Switch to AWS (index 1)
        self.window.provider_dropdown.set_selected(1)
        self.assertEqual(self.window.current_provider, "aws")
        self.assertEqual(self.window.active_provider, self.mock_aws)

        # Switch to Azure (index 2)
        self.window.provider_dropdown.set_selected(2)
        self.assertEqual(self.window.current_provider, "azure")
        self.assertEqual(self.window.active_provider, self.mock_azure)

        # Switch to Ansible (index 3)
        self.window.provider_dropdown.set_selected(3)
        self.assertEqual(self.window.current_provider, "ansible")
        self.assertEqual(self.window.active_provider, self.mock_ansible)

    def test_context_change_clicked(self):
        self.window._on_change_context_clicked(None)
        self.mock_gcp.open_context_dialog.assert_called_once()

    def test_secrets_loaded_rendering(self):
        secrets = [
            SecretItem(
                name="projects/test/secrets/sec1",
                secret_id="sec1",
                description="My secret description",
                labels={"env": "prod"},
                create_time=datetime(2026, 1, 1),
            )
        ]
        self.window._on_secrets_loaded(secrets, None, "gcp")
        self.assertEqual(len(self.window.secrets), 1)
        self.assertEqual(self.window.sidebar_stack.get_visible_child_name(), "list")

    def test_secrets_loaded_error(self):
        self.window._on_secrets_loaded([], "API Error occurred", "gcp")
        self.assertEqual(self.window.sidebar_stack.get_visible_child_name(), "error")
        self.assertTrue(self.window.banner.get_revealed())

    def test_secret_selection_and_versions(self):
        sec = SecretItem(
            name="projects/test/secrets/my-sec",
            secret_id="my-sec",
            description="A secret",
            labels={"app": "web"},
            create_time=datetime(2026, 1, 1),
        )
        self.window._on_secret_selected(sec)
        self.assertEqual(self.window.selected_secret, sec)
        self.assertEqual(self.window.detail_title.get_label(), "my-sec")

        # Load versions
        v1 = SecretVersionItem(
            version_id="1",
            name="projects/test/secrets/my-sec/versions/1",
            state="ENABLED",
            create_time=datetime(2026, 1, 1),
        )
        self.window._on_versions_loaded([v1], None, "projects/test/secrets/my-sec", "gcp")
        self.assertEqual(len(self.window.current_versions), 1)

    def test_payload_loaded_and_reveal_toggle(self):
        # A reply nobody asked for (no reveal/copy intent) is not kept in memory
        self.window._on_payload_loaded("my-secret-token", False, None, "gcp")
        self.assertIsNone(self.window.current_payload)

        # Revealing fetches the value on demand
        self.window.current_versions = [SecretVersionItem(version_id="1", name="v1")]
        self.window.version_dropdown.set_model(Gtk.StringList.new(["Version 1"]))
        self.mock_gcp.access_secret_payload.return_value = ("my-secret-token", False)
        with (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._on_toggle_reveal(None)
        self.assertTrue(self.window.is_payload_revealed)
        self.assertEqual(
            self.window.text_buffer.get_text(
                self.window.text_buffer.get_start_iter(),
                self.window.text_buffer.get_end_iter(),
                True,
            ),
            "my-secret-token",
        )

        # Concealing hides the value and forgets it
        self.window._on_toggle_reveal(None)
        self.assertFalse(self.window.is_payload_revealed)
        self.assertIsNone(self.window.current_payload)
        self.assertIn(
            "•",
            self.window.text_buffer.get_text(
                self.window.text_buffer.get_start_iter(),
                self.window.text_buffer.get_end_iter(),
                True,
            ),
        )

    def test_search_syntax_filters_rows_by_label_and_exclusion(self):
        sec = SecretItem(
            name="projects/test/secrets/db_password",
            secret_id="db_password",
            labels={"env": "prod"},
        )
        self.window.secrets = [sec]
        self.window.sidebar_stack.set_visible_child_name("list")

        def shown(query):
            self.window.search_entry.set_text(query)
            self.window._on_search_changed(self.window.search_entry)
            return self.window.list_store.get_n_items() == 1

        self.assertTrue(shown("label:env=prod"))
        self.assertFalse(shown("label:env=staging"))
        self.assertEqual(self.window.list_stack.get_visible_child_name(), "none")
        self.assertFalse(shown("db -prod"))
        self.assertTrue(shown("db"))
        self.assertEqual(self.window.list_stack.get_visible_child_name(), "results")

    def test_search_box_shortcuts_and_empty_state(self):
        self.assertIsNotNone(self.window.no_results_page.get_parent())
        self.assertIn("label:", self.window.search_entry.get_tooltip_text())

        with patch.object(self.window.search_entry, "grab_focus") as mock_focus:
            self.assertTrue(self.window._focus_search())
            mock_focus.assert_called_once()

        self.window.search_entry.set_text("something")
        self.window.search_entry.emit("stop-search")
        self.assertEqual(self.window.search_entry.get_text(), "")

        self.window._update_sidebar_texts()
        self.assertTrue(self.window.no_results_page.get_title())

    def test_filter_secrets(self):
        sec = SecretItem(
            name="projects/test/secrets/db_password",
            secret_id="db_password",
            description="Database credentials",
            labels={"tier": "backend"},
        )
        self.window.secrets = [sec]

        def count(query):
            self.window.search_entry.set_text(query)
            self.window._on_search_changed(self.window.search_entry)
            return self.window.list_store.get_n_items()

        self.assertEqual(count("db"), 1)
        self.assertEqual(count("credentials"), 1)
        self.assertEqual(count("backend"), 1)
        self.assertEqual(count("nonexistent_term"), 0)

    def test_language_and_theme_toggle(self):
        self.window._toggle_language(self.window.lang_btn)
        self.assertIn(self.window.lang_btn.get_label(), ("ES", "EN"))

        self.window._toggle_theme(self.window.theme_btn)

    def test_toast_notification(self):
        self.window._show_toast("Operation completed successfully")

    def test_lifecycle_success_callbacks(self):
        self.window._on_secret_created_success("new_sec")
        self.window._on_version_added_success()
        self.window._on_version_state_changed_success("1", True)
        self.window._on_version_destroyed_success("1")
        self.window._on_secret_deleted_success("old_sec")

    def test_create_secret_clicked_flow(self):
        with (
            patch.object(self.window.dialogs, "create_secret") as mock_dlg,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._on_create_secret_clicked()
            mock_dlg.assert_called_once()
            on_confirm = mock_dlg.call_args[0][1]
            on_confirm("my_new_secret", "payload123", {"env": "prod"}, "desc")
            self.mock_gcp.create_secret.assert_called_with(
                secret_id="my_new_secret",
                payload_data="payload123",
                labels={"env": "prod"},
                description="desc",
            )

    def test_add_version_clicked_flow(self):
        self.window.selected_secret = SecretItem(
            name="projects/test/secrets/sec1", secret_id="sec1"
        )
        self.window.current_payload = "cached_val"
        with (
            patch.object(self.window.dialogs, "add_version") as mock_dlg,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._on_add_version_clicked()
            mock_dlg.assert_called_once()
            self.assertEqual(mock_dlg.call_args[1].get("current_value"), "cached_val")
            on_confirm = mock_dlg.call_args[0][2]
            on_confirm("new_payload_v2")
            self.mock_gcp.add_secret_version.assert_called_with(
                "projects/test/secrets/sec1", "new_payload_v2"
            )

        # Test fallback when current_payload is None but current_versions exists
        self.window.current_payload = None
        v1 = SecretVersionItem(name="projects/test/secrets/sec1/versions/1", version_id="1")
        self.window.current_versions = [v1]
        self.mock_gcp.access_secret_payload.return_value = ("fallback_val", False)
        with patch.object(self.window.dialogs, "add_version") as mock_dlg:
            self.window._on_add_version_clicked()
            mock_dlg.assert_called_once()
            self.assertEqual(mock_dlg.call_args[1].get("current_value"), "fallback_val")

        # Test fallback when access_secret_payload raises an exception
        self.mock_gcp.access_secret_payload.side_effect = RuntimeError("Failed to fetch")
        with patch.object(self.window.dialogs, "add_version") as mock_dlg:
            self.window._on_add_version_clicked()
            mock_dlg.assert_called_once()
            self.assertIsNone(mock_dlg.call_args[1].get("current_value"))

    def test_toggle_version_state_flow(self):
        v1 = SecretVersionItem(
            name="projects/test/secrets/sec1/versions/1", version_id="1", state="ENABLED"
        )
        with (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._on_toggle_version_state(v1, enable=False)
            self.mock_gcp.toggle_version_state.assert_called_with(
                "projects/test/secrets/sec1/versions/1", False
            )

            self.window._on_toggle_version_state(v1, enable=True)
            self.mock_gcp.toggle_version_state.assert_called_with(
                "projects/test/secrets/sec1/versions/1", True
            )

    def test_destroy_version_clicked_flow(self):
        v1 = SecretVersionItem(
            name="projects/test/secrets/sec1/versions/1", version_id="1", state="DISABLED"
        )
        with (
            patch.object(self.window.dialogs, "confirm_destroy") as mock_dlg,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._on_destroy_version_clicked(v1)
            mock_dlg.assert_called_once()
            on_confirm = mock_dlg.call_args[0][2]
            on_confirm()
            self.mock_gcp.destroy_version.assert_called_with(
                "projects/test/secrets/sec1/versions/1"
            )

    def test_delete_secret_clicked_flow(self):
        self.window.selected_secret = SecretItem(
            name="projects/test/secrets/sec1", secret_id="sec1"
        )
        with (
            patch.object(self.window.dialogs, "confirm_delete") as mock_dlg,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._on_delete_secret_clicked()
            mock_dlg.assert_called_once()
            on_confirm = mock_dlg.call_args[0][2]
            on_confirm()
            self.mock_gcp.delete_secret.assert_called_with("projects/test/secrets/sec1")

    def test_clipboard_operations(self):
        mock_display = MagicMock()
        mock_clipboard = MagicMock()
        mock_display.get_clipboard.return_value = mock_clipboard
        with (
            patch("gi.repository.Gdk.Display.get_default", return_value=mock_display),
            patch("src.ui.windows.actions.secret_content") as content,
        ):
            self.window.current_payload = "super-secret-token"
            self.window._on_copy_payload(None)
            content.assert_called_with("super-secret-token")
            mock_clipboard.set_content.assert_called_with(content.return_value)

            self.window.selected_secret = SecretItem(
                name="projects/test/secrets/s1", secret_id="s1"
            )
            self.window._on_copy_resource_name(None)
            mock_clipboard.set.assert_called_with("projects/test/secrets/s1")

    def test_secret_copy_schedules_clipboard_wipe(self):
        mock_display = MagicMock()
        mock_clipboard = MagicMock()
        mock_display.get_clipboard.return_value = mock_clipboard
        with (
            patch("gi.repository.Gdk.Display.get_default", return_value=mock_display),
            patch("gi.repository.GLib.timeout_add_seconds", return_value=42) as mock_timer,
            patch("gi.repository.GLib.source_remove") as mock_remove,
        ):
            self.window.current_payload = "super-secret-token"
            self.window._on_copy_payload(None)
            mock_timer.assert_called_once_with(30, self.window._clear_clipboard, mock_clipboard)
            self.assertEqual(self.window._clipboard_clear_id, 42)

            # A second copy replaces the pending wipe
            self.window._on_copy_payload(None)
            mock_remove.assert_called_once_with(42)

            # Copying the resource name must not leave a stale wipe of the new content
            self.window.selected_secret = SecretItem(
                name="projects/test/secrets/s1", secret_id="s1"
            )
            self.window._on_copy_resource_name(None)
            self.assertIsNone(self.window._clipboard_clear_id)

    def test_clear_clipboard_only_when_gossip_owns_it(self):
        mock_clipboard = MagicMock()
        mock_clipboard.is_local.return_value = True
        self.window._clear_clipboard(mock_clipboard)
        mock_clipboard.set_content.assert_called_once_with(None)

        other_app_clipboard = MagicMock()
        other_app_clipboard.is_local.return_value = False
        self.window._clear_clipboard(other_app_clipboard)
        other_app_clipboard.set_content.assert_not_called()

    def test_render_versions_list_and_dropdown(self):
        v1 = SecretVersionItem(version_id="1", name="v1", state="ENABLED", stages=["AWSCURRENT"])
        v2 = SecretVersionItem(version_id="2", name="v2", state="DISABLED", stages=["AWSPREVIOUS"])
        v3 = SecretVersionItem(version_id="3", name="v3", state="DESTROYED", stages=[])
        self.window._render_versions_list([v1, v2, v3])

        # Render under AWS provider (supports staging labels)
        self.window.active_provider = self.mock_aws
        self.window._render_versions_list([v1, v2, v3])

        # Test version changed callback
        self.window.current_versions = [v1, v2, v3]
        mock_dd = MagicMock()
        mock_dd.get_selected.return_value = 1
        with patch.object(self.window, "_load_payload_async") as mock_load:
            self.window._on_version_changed(mock_dd, None)
            mock_load.assert_not_called()  # concealed: nothing is fetched

            self.window.version_dropdown.set_model(Gtk.StringList.new(["1", "2", "3"]))
            self.window.version_dropdown.set_selected(1)
            self.window.is_payload_revealed = True
            mock_load.reset_mock()
            self.window._on_version_changed(self.window.version_dropdown, None)
            mock_load.assert_called_with("v2")  # revealed: follows the new version

    def test_update_detail_labels_providers(self):
        # Ansible
        ansible_sec = SecretItem(
            name="vault.yml::my_var",
            secret_id="my_var",
            provider="ansible",
            description="string (12 characters)",
            labels={"type": "str"},
        )
        self.window.selected_secret = ansible_sec
        self.window.active_provider = self.mock_ansible
        self.window._update_detail_labels()

        # Azure
        azure_sec = SecretItem(
            name="https://vault.azure.net/secrets/my-sec",
            secret_id="my-sec",
            provider="azure",
            description="Production DB Password",
            labels={"env": "prod"},
        )
        self.window.selected_secret = azure_sec
        self.window.active_provider = self.mock_azure
        self.window._update_detail_labels()

    def test_async_data_loaders(self):
        with (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._load_secrets_async()
            self.window._load_versions_async("projects/test/secrets/sec1")
            self.window._load_payload_async("projects/test/secrets/sec1/versions/1")

    def test_async_loaders_error_branches(self):
        self.mock_gcp.list_secrets.side_effect = RuntimeError("List secrets error")
        self.mock_gcp.list_versions.side_effect = RuntimeError("List versions error")
        self.mock_gcp.access_secret_payload.side_effect = RuntimeError("Access payload error")

        with (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._load_secrets_async()
            self.window._load_versions_async("projects/test/secrets/sec1")
            self.window._load_payload_async("projects/test/secrets/sec1/versions/1")

        self.mock_gcp.list_secrets.side_effect = None
        self.mock_gcp.list_versions.side_effect = None
        self.mock_gcp.access_secret_payload.side_effect = None

    def test_lifecycle_actions_error_branches(self):
        self.mock_gcp.create_secret.side_effect = RuntimeError("Failed create")
        self.mock_gcp.add_secret_version.side_effect = RuntimeError("Failed add")
        self.mock_gcp.toggle_version_state.side_effect = RuntimeError("Failed toggle")
        self.mock_gcp.destroy_version.side_effect = RuntimeError("Failed destroy")
        self.mock_gcp.delete_secret.side_effect = RuntimeError("Failed delete")

        self.window.selected_secret = SecretItem(
            name="projects/test/secrets/sec1", secret_id="sec1"
        )
        v1 = SecretVersionItem(
            name="projects/test/secrets/sec1/versions/1", version_id="1", state="ENABLED"
        )

        with (
            patch.object(self.window.dialogs, "create_secret") as mock_create_dlg,
            patch.object(self.window.dialogs, "add_version") as mock_add_dlg,
            patch.object(self.window.dialogs, "confirm_destroy") as mock_destroy_dlg,
            patch.object(self.window.dialogs, "confirm_delete") as mock_del_dlg,
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            # Create secret error
            self.window._on_create_secret_clicked()
            mock_create_dlg.call_args[0][1]("id", "p", {})

            # Add version error
            self.window._on_add_version_clicked()
            mock_add_dlg.call_args[0][2]("p")

            # Toggle state error
            self.window._on_toggle_version_state(v1, enable=False)

            # Destroy version error
            self.window._on_destroy_version_clicked(v1)
            mock_destroy_dlg.call_args[0][2]()

            # Delete secret error
            self.window._on_delete_secret_clicked()
            mock_del_dlg.call_args[0][2]()

        self.mock_gcp.create_secret.side_effect = None
        self.mock_gcp.add_secret_version.side_effect = None
        self.mock_gcp.toggle_version_state.side_effect = None
        self.mock_gcp.destroy_version.side_effect = None
        self.mock_gcp.delete_secret.side_effect = None

    def test_edge_cases_and_branch_fallbacks(self):
        # Clipboard with None payload and None secret
        self.window.current_payload = None
        self.window.selected_secret = None
        self.window._on_copy_payload(None)
        self.window._on_copy_resource_name(None)

        # Update labels with None selected_secret
        self.window._update_detail_labels()

        # Update UI texts with secrets and selected_secret present
        sec = SecretItem(name="s1", secret_id="s1")
        self.window.secrets = [sec]
        self.window.selected_secret = sec
        self.window._update_ui_texts()

        # Switch to locked ansible provider
        self.mock_ansible.is_unlocked = False
        with patch.object(self.window, "_on_change_context_clicked") as mock_ctx:
            self.window.provider_dropdown.set_selected(3)
            mock_ctx.assert_called_once()
        self.mock_ansible.is_unlocked = True

        # Render versions under provider without destroy support (e.g. Azure)
        self.window.active_provider = self.mock_azure
        v_en = SecretVersionItem(version_id="1", name="v1", state="ENABLED")
        v_dis = SecretVersionItem(version_id="2", name="v2", state="DISABLED")
        self.window._render_versions_list([v_en, v_dis])

        # Version loaded callback with empty versions list
        self.window.selected_secret = sec
        self.window._on_versions_loaded([], None, "s1", self.window.active_provider.provider_id)
        self.assertIn(
            "[No",
            self.window.text_buffer.get_text(
                self.window.text_buffer.get_start_iter(),
                self.window.text_buffer.get_end_iter(),
                True,
            ),
        )

        # Version loaded callback from stale provider
        self.window._on_versions_loaded([v_en], None, "s1", "stale_provider_id")

    def test_window_100_percent_coverage(self):
        # 1. maximized=True (line 71)
        win_max = MainWindow(
            provider="gcp",
            maximized=True,
            gcp_client=self.mock_gcp,
            aws_client=self.mock_aws,
            azure_client=self.mock_azure,
            ansible_client=self.mock_ansible,
        )
        self.assertIsNotNone(win_max)

        # 2. Provider properties accessors (lines 91, 95, 99, 103)
        self.assertIs(self.window.gcp_client, self.mock_gcp)
        self.assertIs(self.window.aws_client, self.mock_aws)
        self.assertIs(self.window.azure_client, self.mock_azure)
        self.assertIs(self.window.ansible_client, self.mock_ansible)

        # 3. _on_provider_changed out-of-bounds index & same provider (469->exit, 471->exit)
        self.window._on_provider_changed(MagicMock(get_selected=lambda: 999), None)
        self.window._on_provider_changed(MagicMock(get_selected=lambda: 0), None)

        # 4. _on_change_context_clicked callback confirmed (494-495)
        self.mock_gcp.open_context_dialog.side_effect = lambda win, cb: cb()
        with patch.object(self.window, "_load_secrets_async") as mock_lsa:
            self.window._on_change_context_clicked(None)
            mock_lsa.assert_called_once()
        self.mock_gcp.open_context_dialog.side_effect = None

        # 5. _on_secrets_loaded with different provider_id (585)
        self.window._on_secrets_loaded([], None, "different_provider_id")

        # 6. _render_secret_list replacing the existing rows
        self.window.secrets = [SecretItem(name="s1", secret_id="s1")]
        self.window._render_secret_list()
        self.assertEqual(self.window.list_store.get_n_items(), 1)
        self.window.secrets = []
        self.window._render_secret_list()
        self.assertEqual(self.window.list_store.get_n_items(), 0)

        # 7. _on_secret_selected with None does nothing
        self.window._on_secret_selected(None)

        # 9. _update_detail_labels with current_versions present (711)
        self.window.selected_secret = SecretItem(name="s1", secret_id="s1")
        self.window.current_versions = [
            SecretVersionItem(version_id="1", name="v1", state="ENABLED")
        ]
        self.window._update_detail_labels()

        # 10. _on_versions_loaded error toast (742-743)
        self.window._on_versions_loaded(
            [], "Failed fetching versions", "s1", self.window.active_provider.provider_id
        )

        # 11. _load_payload_async worker success path (859)
        self.mock_gcp.access_secret_payload.return_value = ("hello secret payload", False)
        with (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=DummySyncThread),
        ):
            self.window._payload_pending = "reveal"
            self.window._load_payload_async("projects/p/secrets/s/versions/1")
            self.assertEqual(self.window.current_payload, "hello secret payload")

        # 12. _on_payload_loaded with different provider_id (873)
        self.window._on_payload_loaded("payload", False, None, "stale_provider")

        # 13. _render_payload_text with None payload (889-890)
        self.window.current_payload = None
        self.window._render_payload_text()

        # 14. _on_add_version_clicked with no selected secret (937)
        self.window.selected_secret = None
        self.window._on_add_version_clicked()

        # 15. _on_version_state_changed_success with selected_secret (984)
        self.window.selected_secret = SecretItem(name="s1", secret_id="s1")
        with patch.object(self.window, "_load_versions_async") as mock_lva:
            self.window._on_version_state_changed_success("1", True)
            mock_lva.assert_called_with("s1")

        # 16. _on_version_destroyed_success with selected_secret (1007)
        self.window.selected_secret = SecretItem(name="s1", secret_id="s1")
        with patch.object(self.window, "_load_versions_async") as mock_lva:
            self.window._on_version_destroyed_success("1")
            mock_lva.assert_called_with("s1")

        # 17. _on_delete_secret_clicked with no selected secret (1012)
        self.window.selected_secret = None
        self.window._on_delete_secret_clicked()

        # 19. _toggle_theme toggling between light and dark (1084)
        style_mgr = Adw.StyleManager.get_default()
        style_mgr.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        self.window._toggle_theme(None)
        self.window._toggle_theme(None)

        # 20. _toggle_language when error state is active and banner is revealed (577, 586)
        self.window.sidebar_stack.set_visible_child_name("error")
        self.window.banner.set_revealed(True)
        with patch.object(self.window, "_load_secrets_async") as mock_lsa:
            self.window._toggle_language(self.window.lang_btn)
            mock_lsa.assert_called_once()
            self.assertEqual(self.window.banner.get_title(), self.window._get_error_text())

    def test_resolve_icon_name_edge_cases(self):
        from src.ui.window import resolve_icon_name

        # 1. Nonexistent icons return candidates[0]
        name = resolve_icon_name(
            ["nonexistent-xyz-123", "nonexistent-abc-456"], fallback="custom-fallback"
        )
        self.assertEqual(name, "nonexistent-xyz-123")

        # 2. Empty candidates return fallback
        name = resolve_icon_name([], fallback="custom-fallback")
        self.assertEqual(name, "custom-fallback")

        # 3. Without display
        with patch("gi.repository.Gdk.Display.get_default", return_value=None):
            self.assertEqual(resolve_icon_name(["icon-a"], fallback="fb"), "icon-a")
            self.assertEqual(resolve_icon_name([], fallback="fb"), "fb")


if __name__ == "__main__":
    unittest.main()
