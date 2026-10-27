"""Remembers the last provider and context (project, vault, server...) between runs.

Only non-sensitive selections are stored: passwords, tokens and keys are never written.
Precedence at startup is command-line option, then this file, then autodetection.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Mapping, Optional

from src.log import get_logger

log = get_logger(__name__)

STATE_VERSION = 1
MAX_RECENT_CONTEXTS = 5
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 820
_THEMES = ("light", "dark")
_LANGUAGES = ("es", "en")
_SENSITIVE_WORDS = ("password", "passwd", "token", "secret", "key", "credential")


def state_path() -> str:
    """Location of the state file (override with GOSSIP_STATE_FILE)."""
    override = os.environ.get("GOSSIP_STATE_FILE")
    if override:
        return override
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "gossip", "state.json")


def _clean_context(raw: Any) -> Dict[str, str]:
    """Keep only plain string settings and drop anything that looks like a credential."""
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(k): v
        for k, v in raw.items()
        if isinstance(v, str) and v and not any(word in str(k).lower() for word in _SENSITIVE_WORDS)
    }


def _clean_ui(raw: Any) -> Dict[str, Any]:
    """Keep only valid interface preferences (theme, language, window size)."""
    ui: Dict[str, Any] = {}
    if not isinstance(raw, Mapping):
        return ui
    if raw.get("theme") in _THEMES:
        ui["theme"] = raw["theme"]
    if raw.get("language") in _LANGUAGES:
        ui["language"] = raw["language"]
    for key in ("width", "height"):
        value = raw.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 300 <= value <= 10000:
            ui[key] = value
    if isinstance(raw.get("maximized"), bool):
        ui["maximized"] = raw["maximized"]
    return ui


def _empty() -> Dict[str, Any]:
    return {"provider": None, "contexts": {}, "recents": {}, "ui": {}}


def _clean_recents(raw: Any) -> Dict[str, List[Dict[str, str]]]:
    """Per provider, the most recent distinct contexts (newest first), credentials removed."""
    if not isinstance(raw, Mapping):
        return {}
    recents: Dict[str, List[Dict[str, str]]] = {}
    for name, items in raw.items():
        cleaned: List[Dict[str, str]] = []
        for item in items if isinstance(items, list) else []:
            context = _clean_context(item)
            if context and context not in cleaned:
                cleaned.append(context)
        if cleaned:
            recents[str(name)] = cleaned[:MAX_RECENT_CONTEXTS]
    return recents


def remember_recent(
    recents: Mapping[str, List[Dict[str, str]]], provider: str, context: Mapping[str, Any]
) -> Dict[str, List[Dict[str, str]]]:
    """Return ``recents`` with ``context`` moved to the front of the provider's list."""
    result = {name: list(items) for name, items in recents.items()}
    cleaned = _clean_context(context)
    if cleaned:
        items = [c for c in result.get(provider, []) if c != cleaned]
        result[provider] = [cleaned, *items][:MAX_RECENT_CONTEXTS]
    return result


def load() -> Dict[str, Any]:
    """Read the saved state; a missing or damaged file yields an empty state."""
    try:
        with open(state_path(), encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    contexts = raw.get("contexts")
    provider = raw.get("provider")
    return {
        "provider": provider if isinstance(provider, str) else None,
        "contexts": {
            str(name): _clean_context(ctx)
            for name, ctx in (contexts.items() if isinstance(contexts, dict) else [])
        },
        "recents": _clean_recents(raw.get("recents")),
        "ui": _clean_ui(raw.get("ui")),
    }


def save(
    provider: Optional[str],
    contexts: Mapping[str, Any],
    recents: Optional[Mapping[str, Any]] = None,
    ui: Optional[Mapping[str, Any]] = None,
) -> None:
    """Write the state atomically with owner-only permissions; failures are only logged.

    Args:
        provider: Last active provider.
        contexts: Last context of each provider.
        recents: Recently used contexts per provider; the saved ones are kept when omitted.
        ui: Interface preferences (theme, language, window size); kept when omitted.
    """
    previous = load()
    document = {
        "version": STATE_VERSION,
        "provider": provider,
        "contexts": {name: _clean_context(ctx) for name, ctx in contexts.items()},
        "recents": _clean_recents(recents if recents is not None else previous["recents"]),
        "ui": _clean_ui(ui if ui is not None else previous["ui"]),
    }
    path = state_path()
    try:
        folder = os.path.dirname(path) or "."
        os.makedirs(folder, mode=0o700, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".state-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
    except OSError:
        log.debug("could not save state to %s", path, exc_info=True)


def update_ui(**changes: Any) -> None:
    """Merge interface preferences into the saved state, keeping everything else."""
    current = load()
    ui = {**current["ui"], **changes}
    save(current["provider"], current["contexts"], current["recents"], ui)
