from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk
from gi.repository import GLib

from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    GCPSecretClient,
)
from src.models import AzureVaultItem, GCPProjectItem
from src.ui.dialogs import (
    show_about_dialog,
    show_add_version_dialog,
    show_change_ansible_vault_dialog,
    show_change_aws_context_dialog,
    show_change_azure_vault_dialog,
    show_change_project_dialog,
    show_confirm_delete_secret_dialog,
    show_confirm_destroy_version_dialog,
    show_create_secret_dialog,
)


class DummySyncThread:
    def __init__(self, target, *args, **kwargs):
        self.target = target

    def start(self):
        self.target()


def find_children(widget, widget_class):
    results = []
    if isinstance(widget, widget_class):
        results.append(widget)
    if hasattr(widget, "get_child"):
        c = widget.get_child()
        if c:
            results.extend(find_children(c, widget_class))
    if hasattr(widget, "get_first_child"):
        child = widget.get_first_child()
        while child:
            results.extend(find_children(child, widget_class))
            child = child.get_next_sibling()
    return results


class TestDialogs(unittest.TestCase):
    def setUp(self):
        self.parent = Gtk.Window()

    def test_show_about_dialog(self):
        with patch.object(Adw.AboutWindow, "present"):
            show_about_dialog(self.parent)

    def test_show_change_project_dialog_success(self):
        mock_gcp = MagicMock(spec=GCPSecretClient)
        mock_gcp.project_id = "proj-1"
        projects = [
            GCPProjectItem(project_id="proj-1", name="Project One"),
            GCPProjectItem(project_id="proj-2", name="Project Two"),
        ]
        mock_gcp.list_available_projects.return_value = projects
        on_confirm = MagicMock()

        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init), \
             patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)), \
             patch("threading.Thread", side_effect=DummySyncThread):
            show_change_project_dialog(self.parent, mock_gcp, on_confirm)

            self.assertEqual(len(created_dialogs), 1)
            dialog = created_dialogs[0]

            box = dialog.get_extra_child()
            list_boxes = find_children(box, Gtk.ListBox)
            self.assertTrue(len(list_boxes) > 0)
            list_box = list_boxes[0]

            search_entries = find_children(box, Gtk.SearchEntry)
            if search_entries:
                search_entry = search_entries[0]
                # Append plain row to test filter on row without project_id (134)
                plain_row = Gtk.ListBoxRow()
                list_box.append(plain_row)
                search_entry.set_text("Project Two")
                search_entry.emit("search-changed")
                search_entry.set_text("")
                search_entry.emit("search-changed")

            row1 = list_box.get_row_at_index(0)
            row2 = list_box.get_row_at_index(1)

            # Trigger response select before selection (143->exit)
            dialog.emit("response", "select")

            # Trigger selection and response
            list_box.select_row(row1)
            list_box.emit("row-selected", row1)
            dialog.emit("response", "select")
            on_confirm.assert_called_with("proj-1")

            # Trigger row-selected None (118)
            list_box.emit("row-selected", None)

            # Trigger row-activated None (123->exit)
            list_box.emit("row-activated", None)

            # Trigger row-activated
            list_box.emit("row-activated", row2)
            on_confirm.assert_called_with("proj-2")

    def test_show_change_project_dialog_name_equal_and_unmatched_current(self):
        mock_gcp = MagicMock(spec=GCPSecretClient)
        mock_gcp.project_id = "unmatched-proj"
        projects = [
            GCPProjectItem(project_id="same-name", name="same-name"),
        ]
        mock_gcp.list_available_projects.return_value = projects
        on_confirm = MagicMock()
        with patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)), \
             patch("threading.Thread", side_effect=DummySyncThread):
            show_change_project_dialog(self.parent, mock_gcp, on_confirm)

    def test_show_change_project_dialog_error(self):
        mock_gcp = MagicMock(spec=GCPSecretClient)
        mock_gcp.project_id = "proj-1"
        mock_gcp.list_available_projects.side_effect = RuntimeError("Network error")
        on_confirm = MagicMock()

        with patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)), \
             patch("threading.Thread", side_effect=DummySyncThread):
            show_change_project_dialog(self.parent, mock_gcp, on_confirm)

    def test_show_change_aws_context_dialog(self):
        mock_aws = MagicMock(spec=AWSSecretClient)
        mock_aws.profile_name = "unlisted-profile"
        mock_aws.region_name = "unlisted-region"
        mock_aws.list_available_profiles.return_value = ["default", "production"]
        mock_aws.list_available_regions.return_value = ["eu-west-1", "us-east-1"]
        on_confirm = MagicMock()

        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init):
            show_change_aws_context_dialog(self.parent, mock_aws, on_confirm)

        self.assertEqual(len(created_dialogs), 1)
        dialog = created_dialogs[0]

        dialog.emit("response", "select")
        on_confirm.assert_called_once()
        dialog.emit("response", "cancel")

        # Test branches when profile & region are already listed (215->218, 236->239)
        mock_aws_listed = MagicMock(spec=AWSSecretClient)
        mock_aws_listed.profile_name = "default"
        mock_aws_listed.region_name = "us-east-1"
        mock_aws_listed.list_available_profiles.return_value = ["default", "production"]
        mock_aws_listed.list_available_regions.return_value = ["eu-west-1", "us-east-1"]
        show_change_aws_context_dialog(self.parent, mock_aws_listed, on_confirm)

        # Test ValueError branches in dropdown selection (223-224, 244-245)
        class CustomList(list):
            def index(self, *a, **kw):
                raise ValueError("Not found")

        mock_aws_err = MagicMock(spec=AWSSecretClient)
        mock_aws_err.profile_name = "default"
        mock_aws_err.region_name = "us-east-1"
        mock_aws_err.list_available_profiles.return_value = CustomList(["default"])
        mock_aws_err.list_available_regions.return_value = CustomList(["us-east-1"])
        show_change_aws_context_dialog(self.parent, mock_aws_err, on_confirm)

    def test_show_change_azure_vault_dialog_success(self):
        mock_azure = MagicMock(spec=AzureSecretClient)
        mock_azure.vault_name = "my-kv"
        vaults = [
            AzureVaultItem(name="my-kv", vault_uri="https://my-kv.vault.azure.net", location="westeurope"),
            AzureVaultItem(name="secondary-kv", vault_uri="https://sec.vault.azure.net", location="eastus"),
        ]
        mock_azure.list_available_vaults.return_value = vaults
        on_confirm = MagicMock()

        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init), \
             patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)), \
             patch("threading.Thread", side_effect=DummySyncThread):
            show_change_azure_vault_dialog(self.parent, mock_azure, on_confirm)

            self.assertEqual(len(created_dialogs), 1)
            dialog = created_dialogs[0]
            box = dialog.get_extra_child()
            list_boxes = find_children(box, Gtk.ListBox)
            for lb in list_boxes:
                # Test row-activated with custom row having vault_name (315-317)
                test_row = Adw.ActionRow(title="row-vault")
                test_row.vault_name = "row-vault"
                lb.emit("row-activated", test_row)
                # Test row-activated with None (315->exit)
                lb.emit("row-activated", None)

            dialog.emit("response", "select")
            on_confirm.assert_called_with("row-vault")

    def test_show_change_azure_vault_dialog_error_and_manual(self):
        mock_azure = MagicMock(spec=AzureSecretClient)
        mock_azure.vault_name = None
        mock_azure.list_available_vaults.side_effect = RuntimeError("az cli failed")
        on_confirm = MagicMock()

        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init), \
             patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)), \
             patch("threading.Thread", side_effect=DummySyncThread):
            show_change_azure_vault_dialog(self.parent, mock_azure, on_confirm)

            dialog = created_dialogs[0]
            box = dialog.get_extra_child()
            entries = find_children(box, Gtk.Entry)
            if entries:
                # Test response select with empty text (360->exit)
                entries[0].set_text("")
                dialog.emit("response", "select")
                entries[0].set_text("manual-vault")

            dialog.emit("response", "select")
            on_confirm.assert_called_with("manual-vault")
            dialog.emit("response", "cancel")

    def test_show_change_ansible_vault_dialog_success_and_failure(self):
        mock_ansible = MagicMock(spec=AnsibleVaultClient)
        mock_ansible.vault_file = "/path/to/existing_vault.yml"
        mock_ansible.password = "existing_password"
        mock_ansible.password_file = "/path/to/.vault_pass"
        mock_ansible.find_local_vault_files.return_value = ["/path/to/group_vars/vault.yml"]
        on_confirm = MagicMock()

        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init), \
             patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)), \
             patch("threading.Thread", side_effect=DummySyncThread):
            show_change_ansible_vault_dialog(self.parent, mock_ansible, on_confirm)

            dialog = created_dialogs[0]

            # Test browse buttons and dropdown
            box = dialog.get_extra_child()
            buttons = find_children(box, Gtk.Button)

            # 1. Normal browse success
            mock_file_dlg = MagicMock()
            mock_gfile = MagicMock()
            mock_gfile.get_path.return_value = "/path/to/detected/.vault_pass"
            mock_file_dlg.open_finish.return_value = mock_gfile
            with patch("gi.repository.Gtk.FileDialog") as mock_fd_cls:
                mock_fd_inst = MagicMock()
                mock_fd_cls.return_value = mock_fd_inst
                def fake_open(win, cancellable, cb):
                    cb(mock_file_dlg, MagicMock())
                mock_fd_inst.open.side_effect = fake_open
                for btn in buttons:
                    btn.emit("clicked")

            # 2. Browse with gfile without path (408->exit, 464->exit)
            mock_gfile_none = MagicMock()
            mock_gfile_none.get_path.return_value = None
            mock_file_dlg.open_finish.return_value = mock_gfile_none
            with patch("gi.repository.Gtk.FileDialog") as mock_fd_cls:
                mock_fd_inst = MagicMock()
                mock_fd_cls.return_value = mock_fd_inst
                def fake_open(win, cancellable, cb):
                    cb(mock_file_dlg, MagicMock())
                mock_fd_inst.open.side_effect = fake_open
                for btn in buttons:
                    btn.emit("clicked")

            # 3. Browse with exception (410-411, 466-467)
            mock_file_dlg.open_finish.side_effect = Exception("User cancelled file selection")
            with patch("gi.repository.Gtk.FileDialog") as mock_fd_cls:
                mock_fd_inst = MagicMock()
                mock_fd_cls.return_value = mock_fd_inst
                def fake_open(win, cancellable, cb):
                    cb(mock_file_dlg, MagicMock())
                mock_fd_inst.open.side_effect = fake_open
                for btn in buttons:
                    btn.emit("clicked")

            # Dropdown with index 1 and index 0 (428->exit)
            dropdowns = find_children(box, Gtk.DropDown)
            if dropdowns:
                dropdowns[0].set_selected(1)
                dropdowns[0].set_selected(0)

            # Test unlock with empty vault file
            entries = find_children(box, Gtk.Entry)
            if entries:
                entries[0].set_text("")
                dialog.emit("response", "unlock")
                entries[0].set_text("/path/to/vault.yml")

            # Emit unlock successfully
            dialog.emit("response", "unlock")
            on_confirm.assert_called_once()

            # Test failure scenario
            mock_ansible.unlock.side_effect = PermissionError("Decryption failed")
            dialog.emit("response", "unlock")
            dialog.emit("response", "cancel")

        # Test show_change_ansible_vault_dialog without local files and without password_file (421->435, 451->453)
        mock_ansible_no_local = MagicMock(spec=AnsibleVaultClient)
        mock_ansible_no_local.vault_file = None
        mock_ansible_no_local.password = None
        mock_ansible_no_local.password_file = None
        mock_ansible_no_local.find_local_vault_files.return_value = []
        with patch.object(Adw.MessageDialog, "__init__", capture_init):
            show_change_ansible_vault_dialog(self.parent, mock_ansible_no_local, on_confirm)

    def test_show_create_secret_dialog(self):
        for prov in ("gcp", "aws", "azure", "ansible"):
            on_confirm = MagicMock()
            created_dialogs = []
            original_init = Adw.MessageDialog.__init__

            def capture_init(dialog_self, *args, **kwargs):
                original_init(dialog_self, *args, **kwargs)
                created_dialogs.append(dialog_self)

            with patch.object(Adw.MessageDialog, "__init__", capture_init):
                show_create_secret_dialog(self.parent, on_confirm, provider=prov)

            dialog = created_dialogs[0]
            # Emit create without name (should return early)
            dialog.emit("response", "create")
            on_confirm.assert_not_called()

            box = dialog.get_extra_child()
            entries = find_children(box, Gtk.Entry)
            text_views = find_children(box, Gtk.TextView)

            if entries:
                entries[0].set_text("new_secret_key")
                # First test with empty labels (682->689)
                if len(entries) == 2:
                    entries[1].set_text("")
                elif len(entries) >= 3:
                    entries[1].set_text("Database description")
                    entries[2].set_text("")

            if text_views:
                text_views[0].get_buffer().set_text("my_super_secret")

            dialog.emit("response", "create")
            on_confirm.assert_called_once()
            on_confirm.reset_mock()

            # Now test with labels present
            if entries:
                if len(entries) == 2:
                    entries[1].set_text("notag, =emptykey, env=prod, team=core")
                elif len(entries) >= 3:
                    entries[2].set_text("notag, =emptykey, env=prod, team=core")

            dialog.emit("response", "create")
            on_confirm.assert_called_once()
            dialog.emit("response", "cancel")

    def test_show_add_version_dialog(self):
        on_confirm = MagicMock()
        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init):
            show_add_version_dialog(self.parent, "secret_1", on_confirm)

        dialog = created_dialogs[0]
        box = dialog.get_extra_child()
        text_views = find_children(box, Gtk.TextView)
        self.assertTrue(len(text_views) > 0)
        text_view = text_views[0]

        # Emit save with empty buffer -> should not call on_confirm
        dialog.emit("response", "save")
        on_confirm.assert_not_called()

        # Emit save with text
        text_view.get_buffer().set_text("new_payload_version")
        dialog.emit("response", "save")
        on_confirm.assert_called_with("new_payload_version")

        # Emit cancel
        dialog.emit("response", "cancel")

    def test_show_add_version_dialog_with_current_value(self):
        """Test show_add_version_dialog with current_value and checkbox copy toggling."""
        on_confirm = MagicMock()
        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init):
            show_add_version_dialog(self.parent, "secret_1", on_confirm, current_value="previous_secret_content")

        dialog = created_dialogs[0]
        box = dialog.get_extra_child()
        text_views = find_children(box, Gtk.TextView)
        self.assertTrue(len(text_views) > 0)
        text_view = text_views[0]
        buffer = text_view.get_buffer()

        check_buttons = find_children(box, Gtk.CheckButton)
        self.assertEqual(len(check_buttons), 1)
        check_button = check_buttons[0]

        # Initial buffer should be empty
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        self.assertEqual(buffer.get_text(start_iter, end_iter, True), "")

        # Toggle check button ON -> should populate with current_value
        check_button.set_active(True)
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        self.assertEqual(buffer.get_text(start_iter, end_iter, True), "previous_secret_content")

        # Toggle check button OFF without modifying text -> should revert/clear
        check_button.set_active(False)
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        self.assertEqual(buffer.get_text(start_iter, end_iter, True), "")

        # Toggle check button ON again, then edit text
        check_button.set_active(True)
        buffer.set_text("previous_secret_content_appended_info")

        # Toggle check button OFF after modifying text -> should NOT clear the modified text
        check_button.set_active(False)
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        self.assertEqual(buffer.get_text(start_iter, end_iter, True), "previous_secret_content_appended_info")

        # Emit save -> on_confirm should receive the modified payload
        dialog.emit("response", "save")
        on_confirm.assert_called_with("previous_secret_content_appended_info")

    def test_show_confirm_destroy_version_dialog(self):
        on_confirm = MagicMock()
        created_dialogs = []
        original_init = Adw.MessageDialog.__init__

        def capture_init(dialog_self, *args, **kwargs):
            original_init(dialog_self, *args, **kwargs)
            created_dialogs.append(dialog_self)

        with patch.object(Adw.MessageDialog, "__init__", capture_init):
            show_confirm_destroy_version_dialog(self.parent, "v1", on_confirm)

        dialog = created_dialogs[0]
        dialog.emit("response", "cancel")
        on_confirm.assert_not_called()

        dialog.emit("response", "destroy")
        on_confirm.assert_called_once()

    def test_show_confirm_delete_secret_dialog(self):
        for prov in ("gcp", "aws", "azure", "ansible"):
            on_confirm = MagicMock()
            created_dialogs = []
            original_init = Adw.MessageDialog.__init__

            def capture_init(dialog_self, *args, **kwargs):
                original_init(dialog_self, *args, **kwargs)
                created_dialogs.append(dialog_self)

            with patch.object(Adw.MessageDialog, "__init__", capture_init):
                show_confirm_delete_secret_dialog(self.parent, "secret_x", on_confirm, provider=prov)

            dialog = created_dialogs[0]
            dialog.emit("response", "cancel")
            on_confirm.assert_not_called()

            dialog.emit("response", "delete")
            on_confirm.assert_called_once()


if __name__ == "__main__":
    unittest.main()
