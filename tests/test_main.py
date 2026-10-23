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
            "--provider",
            "aws",
            "--aws-profile",
            "prod",
            "--aws-region",
            "eu-west-1",
            "--azure-vault",
            "my-vault",
            "--ansible-vault",
            "my-ansible.yml",
            "--ansible-password-file",
            ".pass",
            "--lang",
            "en",
            "--maximized",
            "--width",
            "1600",
            "--height",
            "1000",
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

    @patch("src.ui.app.run_app", return_value=0)
    @patch.dict("os.environ", {"DISPLAY": ":0"}, clear=True)
    def test_main_renderer_flags(self, mock_run_app):
        import os

        # Test --software-rendering
        test_args_sw = ["gossip", "--software-rendering"]
        with patch.object(sys, "argv", test_args_sw):
            exit_code = main()
            self.assertEqual(exit_code, 0)
            self.assertEqual(os.environ.get("GSK_RENDERER"), "cairo")
            self.assertEqual(os.environ.get("LIBGL_ALWAYS_SOFTWARE"), "1")

        # Test --renderer
        test_args_rend = ["gossip", "--renderer", "ngl"]
        with patch.object(sys, "argv", test_args_rend):
            exit_code = main()
            self.assertEqual(exit_code, 0)
            self.assertEqual(os.environ.get("GSK_RENDERER"), "ngl")

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

    def test_setup_frozen_environment_not_frozen(self):
        from src.main import setup_frozen_environment

        with patch.object(sys, "frozen", False, create=True):
            setup_frozen_environment()

    @patch("os.path.isdir", return_value=True)
    def test_setup_frozen_environment_frozen_with_existing_env(self, mock_isdir):
        import os

        from src.main import setup_frozen_environment

        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "_MEIPASS", "/custom/bundle", create=True):
                with patch.dict(
                    "os.environ",
                    {"GI_TYPELIB_PATH": "/orig/typelib", "GSETTINGS_SCHEMA_DIR": "/orig/schema"},
                ):
                    setup_frozen_environment()
                    self.assertIn("/custom/bundle/girepository-1.0", os.environ["GI_TYPELIB_PATH"])
                    self.assertIn("/orig/typelib", os.environ["GI_TYPELIB_PATH"])
                    self.assertIn(
                        "/custom/bundle/glib-2.0/schemas", os.environ["GSETTINGS_SCHEMA_DIR"]
                    )
                    self.assertIn("/orig/schema", os.environ["GSETTINGS_SCHEMA_DIR"])

    @patch("os.path.isdir", return_value=True)
    def test_setup_frozen_environment_frozen_empty_env(self, mock_isdir):
        import os

        from src.main import setup_frozen_environment

        with patch.object(sys, "frozen", True, create=True):
            with patch.dict("os.environ", {}, clear=True):
                setup_frozen_environment()
                self.assertIn("GI_TYPELIB_PATH", os.environ)
                self.assertIn("GSETTINGS_SCHEMA_DIR", os.environ)

    @patch("os.path.isdir", return_value=False)
    def test_setup_frozen_environment_frozen_no_dirs_found(self, mock_isdir):
        import os

        from src.main import setup_frozen_environment

        with patch.object(sys, "frozen", True, create=True):
            with patch.dict("os.environ", {}, clear=True):
                setup_frozen_environment()
                self.assertNotIn("GI_TYPELIB_PATH", os.environ)
                self.assertNotIn("GSETTINGS_SCHEMA_DIR", os.environ)
                self.assertNotIn("XDG_DATA_DIRS", os.environ)

    @patch("os.path.isdir", return_value=True)
    def test_setup_frozen_environment_repository_prepend_exception(self, mock_isdir):
        from src.main import setup_frozen_environment

        with patch.object(sys, "frozen", True, create=True):
            with patch.dict(sys.modules, {"gi._gi": None}):
                setup_frozen_environment()

    @patch("os.path.isdir", return_value=True)
    def test_setup_frozen_environment_windows(self, mock_isdir):
        import os

        from src.main import setup_frozen_environment

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "platform", "win32"),
            patch.object(sys, "_MEIPASS", "C:\\bundle", create=True),
            patch("os.add_dll_directory", create=True) as mock_add_dll,
            patch.dict("os.environ", {"PATH": "C:\\Windows", "XDG_DATA_DIRS": "C:\\orig\\share"}),
        ):
            setup_frozen_environment()
            mock_add_dll.assert_called_once_with("C:\\bundle")
            self.assertTrue(os.environ["PATH"].startswith("C:\\bundle" + os.pathsep))
            self.assertIn(os.path.join("C:\\bundle", "share"), os.environ["XDG_DATA_DIRS"])
            self.assertIn("C:\\orig\\share", os.environ["XDG_DATA_DIRS"])

    @patch("os.path.isdir", return_value=True)
    def test_setup_frozen_environment_windows_dll_exception_and_empty_path(self, mock_isdir):
        import os

        from src.main import setup_frozen_environment

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "platform", "win32"),
            patch.object(sys, "_MEIPASS", "C:\\bundle", create=True),
            patch("os.add_dll_directory", side_effect=OSError("Failed"), create=True),
            patch.dict("os.environ", {}, clear=True),
        ):
            setup_frozen_environment()
            self.assertEqual(os.environ.get("PATH"), "C:\\bundle")
            self.assertIn("C:\\bundle", os.environ.get("XDG_DATA_DIRS", ""))

    @patch("os.path.isdir", return_value=True)
    def test_setup_frozen_environment_windows_no_add_dll(self, mock_isdir):
        import os

        from src.main import setup_frozen_environment

        with (
            patch.object(sys, "frozen", True, create=True),
            patch.object(sys, "platform", "win32"),
            patch.object(sys, "_MEIPASS", "C:\\bundle", create=True),
            patch.dict("os.environ", {}, clear=True),
        ):
            if hasattr(os, "add_dll_directory"):
                delattr(os, "add_dll_directory")
            setup_frozen_environment()
            self.assertEqual(os.environ.get("PATH"), "C:\\bundle")


if __name__ == "__main__":
    unittest.main()
