from __future__ import annotations

import contextlib
import io
import logging
import sys
import unittest
from unittest.mock import patch

from src import log
from src.main import main


class TestLogging(unittest.TestCase):
    def setUp(self):
        self.root = logging.getLogger("gossip")
        self._handlers = list(self.root.handlers)
        self._level = self.root.level
        self._configured = log._configured
        log._configured = False

    def tearDown(self):
        self.root.handlers[:] = self._handlers
        self.root.setLevel(self._level)
        log._configured = self._configured

    def test_logger_is_namespaced_and_silent_by_default(self):
        logger = log.get_logger("src.demo")
        self.assertEqual(logger.name, "gossip.src.demo")
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            logger.debug("hidden")
        self.assertEqual(captured.getvalue(), "")

    def test_enable_debug_writes_to_stderr_once(self):
        captured = io.StringIO()
        with patch.object(sys, "stderr", captured):
            log.enable_debug()
            log.enable_debug()
            log.get_logger("src.demo").debug("visible")
        self.assertEqual(captured.getvalue().count("visible"), 1)
        self.assertEqual(self.root.level, logging.DEBUG)

    def test_debug_flag_enables_logging_and_reports_environment(self):
        captured = io.StringIO()
        with (
            patch.object(sys, "argv", ["gossip", "--debug", "--self-test"]),
            patch.object(sys, "stderr", captured),
            patch("src.selftest.run_self_test", return_value=0),
        ):
            self.assertEqual(main(), 0)
        self.assertIn("Gossip", captured.getvalue())
        self.assertIn("python", captured.getvalue())

    def test_env_var_enables_logging(self):
        with (
            patch.object(sys, "argv", ["gossip", "--self-test"]),
            patch.dict("os.environ", {"GOSSIP_DEBUG": "1"}),
            patch("src.selftest.run_self_test", return_value=0),
            patch("src.log.enable_debug") as mock_enable,
        ):
            main()
        mock_enable.assert_called_once()


if __name__ == "__main__":
    unittest.main()
