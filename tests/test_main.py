from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from src.main import main


class TestMain(unittest.TestCase):
    @patch("src.ui.app.run_app", return_value=0)
    @patch.dict("os.environ", {"DISPLAY": ":0"})
    def test_main_default_arguments(self, mock_run_app):
        test_args = ["gossip"]
        with patch.object(sys, "argv", test_args):
            exit_code = main()
            self.assertEqual(exit_code, 0)
            mock_run_app.assert_called_once_with(
                provider="gcp",
                project_id=None,
                aws_profile=None,
                aws_region=None,
                azure_vault=None,
                ansible_vault=None,
                ansible_password_file=None,
                width=1280,
                height=820,
                maximized=False,
            )

    @patch("src.ui.app.run_app", return_value=0)
    @patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0"})
    def test_main_custom_flags(self, mock_run_app):
        test_args = [
            "gossip",
            "--provider", "aws",
            "--aws-profile", "prod",
            "--aws-region", "eu-west-1",
            "--azure-vault", "my-vault",
            "--ansible-vault", "my-ansible.yml",
            "--ansible-password-file", ".pass",
            "--lang", "en",
            "--maximized",
            "--width", "1600",
            "--height", "1000",
        ]
        with patch.object(sys, "argv", test_args):
            exit_code = main()
            self.assertEqual(exit_code, 0)
            mock_run_app.assert_called_once_with(
                provider="aws",
                project_id=None,
                aws_profile="prod",
                aws_region="eu-west-1",
                azure_vault="my-vault",
                ansible_vault="my-ansible.yml",
                ansible_password_file=".pass",
                width=1600,
                height=1000,
                maximized=True,
            )

    @patch.dict("os.environ", {}, clear=True)
    def test_main_no_display_server_error(self):
        test_args = ["gossip"]
        with patch.object(sys, "argv", test_args):
            with patch.object(sys, "platform", "linux"):
                exit_code = main()
                self.assertEqual(exit_code, 1)

    @patch("src.ui.app.run_app", return_value=0)
    def test_main_on_non_linux(self, mock_run_app):
        test_args = ["gossip"]
        with patch.object(sys, "argv", test_args):
            with patch.object(sys, "platform", "darwin"):
                exit_code = main()
                self.assertEqual(exit_code, 0)
                mock_run_app.assert_called_once()


if __name__ == "__main__":
    unittest.main()
