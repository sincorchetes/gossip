"""Splitting a secret value into the keys it holds, for the table view."""

from __future__ import annotations

import json
from typing import Dict, Optional


def parse_key_values(text: str) -> Optional[Dict[str, str]]:
    """Return the keys of a JSON-object value, or None when the value is not one.

    Non-string values (numbers, booleans, nested objects) are shown as JSON text, so each
    row can still be copied exactly.

    Args:
        text: The revealed value of a secret.

    Returns:
        Optional[Dict[str, str]]: Key to displayed value, or None for plain text.
    """
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict) or not data:
        return None
    return {
        str(key): value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        for key, value in data.items()
    }
