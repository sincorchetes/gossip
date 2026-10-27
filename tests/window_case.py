"""Shared fixture: a MainWindow wired to mocked providers, reused by feature test modules."""

from __future__ import annotations

import unittest

from tests import test_window


class WindowCase(unittest.TestCase):
    """Base class providing self.window and the provider mocks (no tests of its own)."""

    def setUp(self):
        test_window.TestMainWindow.setUp(self)
