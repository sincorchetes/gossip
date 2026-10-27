"""Helpers shared by providers whose secrets are JSON-like objects behind ``name@version`` names."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

SINGLE_KEY = "value"
_NUMERIC_VERSION = re.compile(r"@(\d+)$")


def parse_rfc3339(value: Optional[str]) -> Optional[datetime]:
    """Parse the RFC 3339 timestamps of HTTP APIs (``Z`` suffix, up to nanosecond precision).

    Args:
        value: Timestamp text; empty, the zero date (``0001-...``) and garbage give None.

    Returns:
        Optional[datetime]: Naive UTC datetime with microsecond precision, or None.
    """
    if not value or value.startswith("0001-"):
        return None
    head, _sep, fraction = value.rstrip("Z").partition(".")
    try:
        return datetime.fromisoformat(f"{head}.{fraction[:6]}" if fraction else head)
    except ValueError:
        return None


def split_numeric_version(name: str, version: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Split ``path@3`` into the secret name and the version number.

    Args:
        name: Secret name, optionally followed by ``@<digits>``.
        version: Explicit version that takes precedence over the suffix.

    Returns:
        Tuple[str, Optional[str]]: The bare name and the version to read, if any.
    """
    match = _NUMERIC_VERSION.search(name)
    if match:
        return name[: match.start()], version or match.group(1)
    return name, version


def parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Return the keys of a non-empty JSON object, or None for any other text."""
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) and obj else None


def format_key_values(data: Dict[str, Any]) -> str:
    """Show stored keys as editable text.

    A lone string under ``value`` is shown as plain text, unless that text itself looks like a
    JSON object: then the wrapper stays visible so saving it again does not restructure it.
    """
    if list(data) == [SINGLE_KEY] and isinstance(data[SINGLE_KEY], str):
        if parse_json_object(data[SINGLE_KEY]) is None:
            return data[SINGLE_KEY]
    return json.dumps(data, indent=2, ensure_ascii=False)
