"""Line-based comparison of two secret payloads for the version diff view."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import List

# Kinds of rendered diff lines
HEADER = "header"
HUNK = "hunk"
ADDED = "added"
REMOVED = "removed"
CONTEXT = "context"


@dataclass(frozen=True)
class DiffLine:
    """A single rendered line of a unified diff.

    Attributes:
        kind: One of HEADER, HUNK, ADDED, REMOVED or CONTEXT.
        text: The line content, including its leading diff marker.
    """

    kind: str
    text: str


def normalize_payload(text: str) -> str:
    """Pretty-print JSON payloads with sorted keys so formatting-only changes do not show up.

    Args:
        text: Raw secret value.

    Returns:
        str: Canonical JSON text when the value is a JSON object or array, otherwise the
        original text unchanged.
    """
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        try:
            return json.dumps(json.loads(stripped), indent=2, sort_keys=True, ensure_ascii=False)
        except ValueError:
            pass
    return text


def diff_payloads(old: str, new: str, old_label: str, new_label: str) -> List[DiffLine]:
    """Compute a unified diff between two payloads.

    Args:
        old: Payload of the older/base version.
        new: Payload of the newer/compared version.
        old_label: Label shown in the '---' header.
        new_label: Label shown in the '+++' header.

    Returns:
        List[DiffLine]: Rendered diff lines; empty when both payloads are equivalent.
    """
    old_lines = normalize_payload(old).splitlines()
    new_lines = normalize_payload(new).splitlines()
    result: List[DiffLine] = []
    for line in difflib.unified_diff(old_lines, new_lines, old_label, new_label, lineterm="", n=3):
        if line.startswith(("---", "+++")):
            kind = HEADER
        elif line.startswith("@@"):
            kind = HUNK
        elif line.startswith("+"):
            kind = ADDED
        elif line.startswith("-"):
            kind = REMOVED
        else:
            kind = CONTEXT
        result.append(DiffLine(kind, line))
    return result
