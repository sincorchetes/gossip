"""Run a provider call off the GTK thread and deliver its outcome back on it."""

from __future__ import annotations

import threading
from typing import Callable, TypeVar

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

T = TypeVar("T")


def _deliver(callback: Callable[..., object], *args: object) -> bool:
    """Run a callback on the main loop once (returning False removes the idle source)."""
    callback(*args)
    return GLib.SOURCE_REMOVE


def run_in_background(
    task: Callable[[], T],
    on_done: Callable[[T], object],
    on_error: Callable[[Exception], object],
) -> None:
    """Call ``task`` in a daemon thread, then report back on the GTK main loop.

    Args:
        task: Blocking work (a provider call). It must not touch widgets.
        on_done: Receives the result of ``task``; runs on the main loop.
        on_error: Receives the exception ``task`` raised; runs on the main loop.
    """

    def worker() -> None:
        try:
            result = task()
        except Exception as exc:
            GLib.idle_add(_deliver, on_error, exc)
        else:
            GLib.idle_add(_deliver, on_done, result)

    threading.Thread(target=worker, daemon=True).start()
