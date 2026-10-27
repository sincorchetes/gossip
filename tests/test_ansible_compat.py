from __future__ import annotations

import ctypes
import locale
import multiprocessing
import sys
import unittest
from unittest.mock import MagicMock, patch

from src.providers.ansible import compat
from src.providers.ansible.compat import (
    _MockLibc,
    _MockLibcFunc,
    ansible_import_context,
    ensure_windows_runtime,
    scoped_stdlib_patches,
)


class TestMockLibc(unittest.TestCase):
    def test_mock_libc_func(self):
        func = _MockLibcFunc(default_ret=42)
        self.assertEqual(func("hello"), 5)
        self.assertEqual(func(123), 42)
        self.assertEqual(func(), 42)

    def test_mock_libc(self):
        libc = _MockLibc()
        self.assertEqual(libc.wcwidth("a"), 1)
        self.assertEqual(libc.wcswidth("test", 10), 4)
        self.assertEqual(libc["wcwidth"], libc.wcwidth)
        self.assertEqual(libc["unknown_symbol"](), 0)
        self.assertTrue(callable(libc.non_existent_symbol))


class TestEnsureWindowsRuntime(unittest.TestCase):
    def test_none_streams_are_replaced_by_writers(self):
        out, err = sys.stdout, sys.stderr
        try:
            sys.stdout = None
            sys.stderr = None
            ensure_windows_runtime()
            self.assertTrue(callable(sys.stdout.write))
            self.assertTrue(callable(sys.stderr.write))
        finally:
            sys.stdout, sys.stderr = out, err

    def test_missing_unix_modules_are_stubbed_and_existing_ones_kept(self):
        names = ("fcntl", "termios", "tty", "pwd", "grp")
        saved = {name: sys.modules.get(name) for name in names}
        try:
            for name in names:
                sys.modules.pop(name, None)
            ensure_windows_runtime()

            self.assertEqual(sys.modules["fcntl"].fcntl(1), 0)
            self.assertEqual(sys.modules["fcntl"].flock(1, 0), 0)
            self.assertEqual(sys.modules["fcntl"].lockf(1, 0), 0)
            self.assertIsInstance(sys.modules["fcntl"].ioctl(1, 0), bytes)
            self.assertEqual(sys.modules["termios"].tcgetattr(0), [0, 0, 0, 0, 0, 0, [0] * 32])
            self.assertIsNone(sys.modules["termios"].tcsetattr(0, 0, []))
            self.assertIsNone(sys.modules["termios"].tcflush(0, 0))
            self.assertIsNone(sys.modules["tty"].setraw(0))
            self.assertIsNone(sys.modules["tty"].setcbreak(0))
            self.assertEqual(sys.modules["pwd"].getpwuid(1000)[0], "user")
            self.assertEqual(sys.modules["pwd"].getpwnam("user")[0], "user")
            self.assertEqual(sys.modules["grp"].getgrgid(1000)[0], "user")
            self.assertEqual(sys.modules["grp"].getgrnam("user")[0], "user")

            stub = sys.modules["fcntl"]
            ensure_windows_runtime()
            self.assertIs(sys.modules["fcntl"], stub)  # second call is a no-op
        finally:
            for name, module in saved.items():
                if module is not None:
                    sys.modules[name] = module
                else:
                    sys.modules.pop(name, None)


class TestSwap(unittest.TestCase):
    def test_own_attribute_is_restored(self):
        holder = type("Holder", (), {})()
        holder.value = 1
        restore = compat._swap(holder, "value", 2)
        self.assertEqual(holder.value, 2)
        restore()
        self.assertEqual(holder.value, 1)

    def test_inherited_attribute_is_removed_again(self):
        class Base:
            def method(self):
                return "base"

        obj = Base()
        restore = compat._swap(obj, "method", lambda: "patched")
        self.assertEqual(obj.method(), "patched")
        restore()
        self.assertNotIn("method", vars(obj))
        self.assertEqual(obj.method(), "base")


class TestScopedStdlibPatches(unittest.TestCase):
    def test_everything_is_restored_after_the_block(self):
        before = (
            ctypes.CDLL.__getitem__,
            locale.getlocale,
            multiprocessing.get_context,
            "LoadLibrary" in vars(ctypes.cdll),
        )
        with scoped_stdlib_patches():
            self.assertIsNot(ctypes.CDLL.__getitem__, before[0])
            self.assertIsNot(locale.getlocale, before[1])
            self.assertIn("LoadLibrary", vars(ctypes.cdll))
        after = (
            ctypes.CDLL.__getitem__,
            locale.getlocale,
            multiprocessing.get_context,
            "LoadLibrary" in vars(ctypes.cdll),
        )
        self.assertEqual(before, after)

    def test_everything_is_restored_when_the_block_raises(self):
        original_getlocale = locale.getlocale
        with self.assertRaises(RuntimeError):
            with scoped_stdlib_patches():
                raise RuntimeError("import failed")
        self.assertIs(locale.getlocale, original_getlocale)
        self.assertNotIn("LoadLibrary", vars(ctypes.cdll))

    def test_load_library_fallbacks(self):
        loader = MagicMock(return_value="real-library")
        with patch.object(ctypes.cdll, "LoadLibrary", loader, create=True):
            with scoped_stdlib_patches():
                self.assertIsInstance(ctypes.cdll.LoadLibrary(None), _MockLibc)
                self.assertIsInstance(ctypes.cdll.LoadLibrary("c"), _MockLibc)
                self.assertIsInstance(ctypes.cdll.LoadLibrary("libc"), _MockLibc)
                with patch("sys.platform", "win32"):
                    self.assertIsInstance(ctypes.cdll.LoadLibrary("msvcrt.dll"), _MockLibc)

                self.assertEqual(ctypes.cdll.LoadLibrary("custom_dll"), "real-library")
                loader.assert_called_with("custom_dll")

                loader.side_effect = OSError("DLL not found")
                with patch("sys.platform", "win32"):
                    self.assertIsInstance(ctypes.cdll.LoadLibrary("missing.dll"), _MockLibc)
                with patch("sys.platform", "linux"):
                    with self.assertRaises(OSError):
                        ctypes.cdll.LoadLibrary("missing.dll")

    def test_missing_wcwidth_symbols_are_supplied(self):
        failing = MagicMock(side_effect=AttributeError("Symbol not found"))
        with patch.object(ctypes.CDLL, "__getitem__", failing):
            with scoped_stdlib_patches():
                library = MagicMock(spec=ctypes.CDLL)
                self.assertIsInstance(ctypes.CDLL.__getitem__(library, "wcwidth"), _MockLibcFunc)
                self.assertIsInstance(ctypes.CDLL.__getitem__(library, "wcswidth"), _MockLibcFunc)
                with self.assertRaises(AttributeError):
                    ctypes.CDLL.__getitem__(library, "other_symbol")

    def test_getlocale_always_reports_utf8(self):
        cases = {
            (None, None): ("en_US", "UTF-8"),
            ("en_US", "1252"): ("en_US", "UTF-8"),
            ("es_ES", "utf-8"): ("es_ES", "utf-8"),
        }
        for reported, expected in cases.items():
            with self.subTest(reported=reported):
                with patch.object(locale, "getlocale", MagicMock(return_value=reported)):
                    with scoped_stdlib_patches():
                        self.assertEqual(locale.getlocale(), expected)

    def test_fork_context_falls_back_when_fork_is_unavailable(self):
        original = multiprocessing.get_context
        with patch("multiprocessing.get_all_start_methods", return_value=["spawn"]):
            with scoped_stdlib_patches():
                self.assertIsNotNone(multiprocessing.get_context("fork"))
                self.assertIsNotNone(multiprocessing.get_context("spawn"))
                self.assertIsNotNone(multiprocessing.get_context(None))
        self.assertIs(multiprocessing.get_context, original)

    def test_get_context_is_left_alone_when_fork_exists(self):
        original = multiprocessing.get_context
        with patch("multiprocessing.get_all_start_methods", return_value=["fork", "spawn"]):
            with scoped_stdlib_patches():
                self.assertIs(multiprocessing.get_context, original)


class TestAnsibleImportContext(unittest.TestCase):
    def test_ansible_fixes_are_applied_after_a_successful_import(self):
        with patch("src.providers.ansible.shims.patch_ansible_core") as fixes:
            with ansible_import_context():
                fixes.assert_not_called()
        fixes.assert_called_once()

    def test_ansible_fixes_are_skipped_when_the_import_fails(self):
        with patch("src.providers.ansible.shims.patch_ansible_core") as fixes:
            with self.assertRaises(ImportError):
                with ansible_import_context():
                    raise ImportError("no ansible")
        fixes.assert_not_called()

    def test_context_leaves_no_process_wide_patches(self):
        getlocale, getitem = locale.getlocale, ctypes.CDLL.__getitem__
        with ansible_import_context():
            pass
        self.assertIs(locale.getlocale, getlocale)
        self.assertIs(ctypes.CDLL.__getitem__, getitem)

    def test_nested_contexts_unwind_in_order(self):
        getlocale = locale.getlocale
        with ansible_import_context():
            with ansible_import_context():
                pass
        self.assertIs(locale.getlocale, getlocale)


class TestPatchAnsibleCore(unittest.TestCase):
    def test_config_yaml_file_lookup_falls_back_to_the_bundle(self):
        import ansible.config.manager as acm

        from src.providers.ansible.shims import patch_ansible_core

        original = acm.ConfigManager._read_config_yaml_file
        flag = getattr(acm.ConfigManager, "_gossip_yaml_patched", False)
        mock_orig = MagicMock(return_value={"ANSIBLE_TEST": "ok"})
        try:
            acm.ConfigManager._gossip_yaml_patched = False
            acm.ConfigManager._read_config_yaml_file = mock_orig
            patch_ansible_core()
            manager = MagicMock()

            with patch("os.path.exists", return_value=True):
                result = acm.ConfigManager._read_config_yaml_file(manager, "/path/to/base.yml")
            self.assertEqual(result, {"ANSIBLE_TEST": "ok"})
            mock_orig.assert_called_with(manager, "/path/to/base.yml")

            mock_orig.reset_mock()
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", "/bundle/dir", create=True),
                patch(
                    "os.path.exists",
                    side_effect=lambda p: p == "/bundle/dir/_internal/ansible/config/base.yml",
                ),
            ):
                acm.ConfigManager._read_config_yaml_file(manager, b"/missing/base.yml")
            mock_orig.assert_called_with(manager, "/bundle/dir/_internal/ansible/config/base.yml")

            mock_orig.reset_mock()
            with (
                patch.object(sys, "frozen", False, create=True),
                patch("os.path.exists", return_value=False),
            ):
                acm.ConfigManager._read_config_yaml_file(manager, "/missing/base.yml")
            mock_orig.assert_called_with(manager, "/missing/base.yml")

            patched = acm.ConfigManager._read_config_yaml_file
            patch_ansible_core()  # already patched: no-op
            self.assertIs(acm.ConfigManager._read_config_yaml_file, patched)
        finally:
            acm.ConfigManager._read_config_yaml_file = original
            acm.ConfigManager._gossip_yaml_patched = flag

    def test_display_errors_are_swallowed(self):
        import ansible.utils.display as aud

        from src.providers.ansible.shims import patch_ansible_core

        original = aud.Display.display
        flag = getattr(aud.Display, "_gossip_display_patched", False)
        mock_display = MagicMock(
            side_effect=AttributeError("'NoneType' object has no attribute 'write'")
        )
        try:
            aud.Display._gossip_display_patched = False
            aud.Display.display = mock_display
            patch_ansible_core()
            instance = MagicMock(spec=aud.Display)

            self.assertIsNone(aud.Display.display(instance, "warning", stderr=True))
            mock_display.side_effect = OSError("Stream closed")
            self.assertIsNone(aud.Display.display(instance, "error"))
            mock_display.side_effect = None
            mock_display.return_value = "ok"
            self.assertEqual(aud.Display.display(instance, "normal"), "ok")

            patched = aud.Display.display
            patch_ansible_core()
            self.assertIs(aud.Display.display, patched)
        finally:
            aud.Display.display = original
            aud.Display._gossip_display_patched = flag


class TestNoProcessWidePatchesAfterImport(unittest.TestCase):
    def test_importing_the_providers_leaves_the_standard_library_untouched(self):
        import os
        import subprocess

        code = (
            "import ctypes, locale, multiprocessing\n"
            "import src.providers\n"
            "assert locale.getlocale.__module__ == 'locale', locale.getlocale\n"
            "assert 'LoadLibrary' not in vars(ctypes.cdll)\n"
            "assert ctypes.CDLL.__getitem__.__module__ in ('ctypes', None), ctypes.CDLL.__getitem__\n"
            "assert multiprocessing.get_context.__module__.startswith('multiprocessing')\n"
            "print('untouched')\n"
        )
        root = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, cwd=root
        )
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        self.assertIn("untouched", result.stdout)


if __name__ == "__main__":
    unittest.main()
