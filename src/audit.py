"""Optional local audit trail of what the user reveals, copies and changes.

One JSON object per line: time, provider, context, action and secret name. Secret values are
never written, and keys that could hold them are dropped. The file is private to the user.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

from src import state
from src.log import get_logger

log = get_logger(__name__)

ENV_VAR = "GOSSIP_AUDIT_LOG"
MAX_BYTES = 5 * 1024 * 1024
_FORBIDDEN = ("value", "payload", "password", "token", "secret_value", "content")


def default_path() -> str:
    """Audit file next to the state file."""
    return os.path.join(os.path.dirname(state.state_path()), "audit.jsonl")


def active_path() -> Optional[str]:
    """Where to write, or None when auditing is off (set by --audit-log or GOSSIP_AUDIT_LOG)."""
    setting = os.environ.get(ENV_VAR, "").strip()
    if not setting or setting.lower() in ("0", "false", "no", "off"):
        return None
    if setting.lower() in ("1", "true", "yes", "on"):
        return default_path()
    return os.path.expanduser(setting)


def _rotate(path: str) -> None:
    try:
        if os.path.getsize(path) >= MAX_BYTES:
            os.replace(path, path + ".1")
    except OSError:
        pass


def record(
    action: str, provider: str, context: str = "", secret: Optional[str] = None, **extra: Any
) -> None:
    """Append one event; failures are only logged so auditing never breaks the application.

    Args:
        action: What happened (reveal, copy, create, delete, ...).
        provider: Provider identifier.
        context: Human-readable project / vault / server the action ran against.
        secret: Name of the secret involved (never its value).
        **extra: Further details such as a version or a count; value-like keys are dropped.
    """
    path = active_path()
    if not path:
        return
    event = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": provider,
        "context": context,
        "action": action,
    }
    if secret is not None:
        event["secret"] = secret
    event.update(
        {k: v for k, v in extra.items() if not any(word in k.lower() for word in _FORBIDDEN)}
    )
    try:
        os.makedirs(os.path.dirname(path) or ".", mode=0o700, exist_ok=True)
        _rotate(path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        log.debug("could not write audit log %s", path, exc_info=True)
