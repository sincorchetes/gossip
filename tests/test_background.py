from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

from gi.repository import GLib

from src.i18n import set_language
from src.ui.background import _deliver, run_in_background
from tests.window_case import WindowCase


class TestRunInBackground(unittest.TestCase):
    def run_with_captured_idle(self, task):
        """Run the task in a real thread; collect what it schedules on the main loop."""
        scheduled, finished = [], threading.Event()

        def capture(function, *args):
            scheduled.append((function, args))
            finished.set()

        on_done, on_error = MagicMock(), MagicMock()
        with patch("gi.repository.GLib.idle_add", side_effect=capture):
            run_in_background(task, on_done, on_error)
            self.assertTrue(finished.wait(5))
        return scheduled, on_done, on_error

    def test_the_task_runs_off_the_calling_thread_and_the_result_is_delivered_on_idle(self):
        threads = []
        scheduled, on_done, on_error = self.run_with_captured_idle(
            lambda: threads.append(threading.current_thread()) or "result"
        )
        self.assertIsNot(threads[0], threading.main_thread())
        self.assertTrue(threads[0].daemon)
        on_done.assert_not_called()  # nothing runs until the main loop gets to it
        function, args = scheduled[0]
        self.assertTrue(function is _deliver and args[0] is on_done and args[1] == "result")
        on_error.assert_not_called()

    def test_failures_are_delivered_to_the_error_handler(self):
        error = RuntimeError("boom")

        def failing():
            raise error

        scheduled, on_done, on_error = self.run_with_captured_idle(failing)
        function, args = scheduled[0]
        self.assertTrue(args[0] is on_error and args[1] is error)
        on_done.assert_not_called()

    def test_delivery_calls_back_once_and_removes_the_idle_source(self):
        callback = MagicMock()
        self.assertEqual(_deliver(callback, 1, 2), GLib.SOURCE_REMOVE)
        callback.assert_called_once_with(1, 2)


class TestWindowDefault(WindowCase):
    def test_failures_become_a_toast_by_default(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        with (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=lambda target, **_k: MagicMock(start=target)),
            patch.object(self.window, "_show_toast") as toast,
        ):

            def failing():
                raise RuntimeError("denied")

            self.window._run_in_background(failing, MagicMock())
            toast.assert_called_once_with("Error: denied")
            done = MagicMock()
            self.window._run_in_background(lambda: 7, done)
            done.assert_called_once_with(7)

    def test_a_custom_error_handler_replaces_the_toast(self):
        handler = MagicMock()
        with (
            patch("gi.repository.GLib.idle_add", side_effect=lambda fn, *a: fn(*a)),
            patch("threading.Thread", side_effect=lambda target, **_k: MagicMock(start=target)),
            patch.object(self.window, "_show_toast") as toast,
        ):
            self.window._run_in_background(lambda: 1 / 0, MagicMock(), handler)
        handler.assert_called_once()
        toast.assert_not_called()


if __name__ == "__main__":
    unittest.main()
