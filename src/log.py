"""Opt-in diagnostic logging for Gossip (enable with --debug or GOSSIP_DEBUG=1)."""

from __future__ import annotations

import collections
import logging
import os
import re
import sys
from typing import Deque, List

_ROOT = "gossip"
_configured = False
RING_SIZE = 200

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(token|password|passwd|secret|authorization|api[_-]?key|x-vault-token)\b(\s*[=:]\s*)(\S+)"
)
_AUTHORIZATION = re.compile(r"(?i)\b(authorization)(\s*[=:]\s*).*")
_BEARER = re.compile(r"(?i)\b(bearer|basic)\s+\S+")
_URL_USERINFO = re.compile(r"(\w+://)[^/\s:@]++:[^/\s@]++@")
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9+/_=-]{32,}\b")


def redact(text: str) -> str:
    """Remove anything that looks like a credential, and the user's home directory, from text."""
    text = _URL_USERINFO.sub(r"\1***@", text)
    text = _AUTHORIZATION.sub(r"\1\2***", text)
    text = _BEARER.sub(r"\1 ***", text)
    text = _SECRET_ASSIGNMENT.sub(r"\1\2***", text)
    text = _LONG_TOKEN.sub("***", text)
    home = os.path.expanduser("~")
    return text.replace(home, "~") if home and home != "~" else text


class RingHandler(logging.Handler):
    """Keeps the most recent log lines in memory, redacted, for the diagnostics report."""

    def __init__(self, size: int = RING_SIZE) -> None:
        super().__init__(level=logging.DEBUG)
        self.lines: Deque[str] = collections.deque(maxlen=size)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        """Store the formatted, redacted record."""
        try:
            self.lines.append(redact(self.format(record)))
        except Exception:  # never let logging break the application
            self.handleError(record)


_ring = RingHandler()
_logger = logging.getLogger(_ROOT)
_logger.addHandler(logging.NullHandler())
_logger.addHandler(_ring)
_logger.setLevel(logging.DEBUG)


def recent_log() -> List[str]:
    """The last diagnostic lines, already redacted."""
    return list(_ring.lines)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'gossip' namespace.

    Args:
        name: Usually the calling module's __name__.

    Returns:
        logging.Logger: Logger that is silent unless debug logging has been enabled.
    """
    return logging.getLogger(f"{_ROOT}.{name}")


def enable_debug() -> None:
    """Send DEBUG-level diagnostics to stderr (idempotent)."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger(_ROOT).addHandler(handler)
    _configured = True
