"""Read-only mode: browsing and copying stay available, every change is blocked."""

from __future__ import annotations

import functools
import os
from typing import Any, Callable

from src.i18n import _

ENV_VAR = "GOSSIP_READ_ONLY"


def is_read_only() -> bool:
    """True when --read-only or GOSSIP_READ_ONLY=1 is in effect."""
    return os.environ.get(ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


LOCK_VAR = "GOSSIP_READ_ONLY_LOCKED"


def is_locked() -> bool:
    """True when read-only mode was requested with --read-only and cannot be turned off."""
    return os.environ.get(LOCK_VAR, "").strip() == "1"


def set_read_only(enabled: bool) -> None:
    """Turn read-only mode on or off for the running application."""
    if not enabled and is_locked():
        return
    os.environ[ENV_VAR] = "1" if enabled else "0"


def blocks_writes(method: Callable[..., Any]) -> Callable[..., Any]:
    """Decorate a window action so it only shows a notice in read-only mode."""

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        if is_read_only():
            self._show_toast(_("Read-only mode: changes are disabled"))
            return None
        return method(self, *args, **kwargs)

    return wrapper
