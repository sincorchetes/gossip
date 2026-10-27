from __future__ import annotations

import fcntl
import struct
import sys
import termios
import unittest
from unittest.mock import patch

from src.providers.ansible.compat import tty_ioctl_guard


def _enotty(fd, request, arg=0, mutate_flag=True):
    raise OSError(25, "Inappropriate ioctl for device")


@unittest.skipIf(sys.platform == "win32", "fcntl is POSIX only")
class TestTtyIoctlGuard(unittest.TestCase):
    def test_window_size_failure_returns_zeroed_buffer(self):
        with patch.object(fcntl, "ioctl", _enotty), tty_ioctl_guard():
            result = fcntl.ioctl(1, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        self.assertEqual(struct.unpack("HHHH", result), (0, 0, 0, 0))

    def test_other_requests_still_raise(self):
        with patch.object(fcntl, "ioctl", _enotty), tty_ioctl_guard():
            with self.assertRaises(OSError):
                fcntl.ioctl(1, termios.TIOCGWINSZ, 5)

    def test_success_is_passed_through(self):
        def working(fd, request, arg=0, mutate_flag=True):
            return b"ok"

        with patch.object(fcntl, "ioctl", working), tty_ioctl_guard():
            self.assertEqual(fcntl.ioctl(1, termios.TIOCGWINSZ, b"\0"), b"ok")

    def test_original_ioctl_is_restored_on_exit_even_after_error(self):
        with patch.object(fcntl, "ioctl", _enotty):
            with self.assertRaises(RuntimeError):
                with tty_ioctl_guard():
                    self.assertIsNot(fcntl.ioctl, _enotty)
                    raise RuntimeError("boom")
            self.assertIs(fcntl.ioctl, _enotty)

    def test_no_process_wide_patch_remains_after_importing_providers(self):
        import src.providers.ansible  # noqa: F401

        self.assertFalse(getattr(fcntl.ioctl, "_gossip_guarded", False))
        self.assertEqual(fcntl.ioctl.__module__, "fcntl")


class TestWindowsPassthrough(unittest.TestCase):
    def test_block_runs_unchanged_on_windows(self):
        with patch.object(sys, "platform", "win32"):
            with tty_ioctl_guard():
                executed = True
        self.assertTrue(executed)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(sys.platform == "win32", "fcntl is POSIX only")
class TestImportOnBrokenTty(unittest.TestCase):
    def test_importing_ansible_survives_tty_that_rejects_window_size(self):
        import os
        import subprocess

        code = (
            "import os, fcntl\n"
            "os.isatty = lambda fd: True\n"
            "def bad(*a, **k):\n"
            "    raise OSError(25, 'Inappropriate ioctl for device')\n"
            "fcntl.ioctl = bad\n"
            "import src.providers.ansible\n"
            "print('imported')\n"
        )
        root = os.path.join(os.path.dirname(__file__), "..")
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, cwd=root
        )
        self.assertEqual(result.returncode, 0, result.stderr[-600:])
        self.assertIn("imported", result.stdout)
