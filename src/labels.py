"""Reading and writing the key=value labels / tags typed in dialogs."""

from __future__ import annotations

from typing import Dict


def parse_labels(text: str) -> Dict[str, str]:
    """Parse ``key=value`` pairs separated by new lines or commas.

    Entries without a key are ignored and values may be empty. Whitespace around keys and
    values is dropped.

    Args:
        text: Text typed by the user.

    Returns:
        Dict[str, str]: The labels, in the order they were written.
    """
    labels: Dict[str, str] = {}
    for line in text.splitlines():
        for part in line.split(","):
            key, sep, value = part.partition("=")
            if sep and key.strip():
                labels[key.strip()] = value.strip()
    return labels


def format_labels(labels: Dict[str, str]) -> str:
    """Render labels one per line, the format parse_labels reads back."""
    return "\n".join(f"{key}={value}" for key, value in labels.items())
