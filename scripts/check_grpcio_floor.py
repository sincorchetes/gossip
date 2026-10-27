#!/usr/bin/env python3
"""Warn, then fail, when the installed grpcio is older than the floor Google will require.

Google Cloud Python packages will raise their minimum grpcio to 1.83 in April 2027. The Windows
build gets grpcio from MSYS2, which may lag, so this check turns that date into an alarm:
it stays silent until January 2027, warns until the deadline and fails the build after it.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from importlib import metadata
from typing import Optional, Tuple

FLOOR = (1, 83)
WARN_FROM = date(2027, 1, 1)
DEADLINE = date(2027, 4, 1)


def parse_version(text: str) -> Tuple[int, int]:
    """Return (major, minor) from a version string such as '1.82.0'."""
    match = re.match(r"(\d+)\.(\d+)", text)
    if not match:
        raise ValueError(f"Unrecognised grpcio version: {text!r}")
    return int(match.group(1)), int(match.group(2))


def evaluate(version: str, today: date) -> Tuple[str, str]:
    """Decide what to report for an installed grpcio version.

    Args:
        version: Installed grpcio version.
        today: Current date.

    Returns:
        Tuple[str, str]: ("ok" | "warning" | "error", human readable message).
    """
    floor = ".".join(map(str, FLOOR))
    if parse_version(version) >= FLOOR:
        return "ok", f"grpcio {version} satisfies the >= {floor} requirement"
    if today >= DEADLINE:
        return "error", (
            f"grpcio {version} is older than {floor}, which Google Cloud packages now require"
        )
    if today >= WARN_FROM:
        return "warning", (
            f"grpcio {version} is older than {floor}, required from {DEADLINE.isoformat()}: "
            "check whether MSYS2 has updated it"
        )
    return "ok", f"grpcio {version} is below {floor}, required only from {DEADLINE.isoformat()}"


def main(argv: list[str], today: Optional[date] = None) -> int:
    """Check the installed grpcio and print a GitHub Actions annotation when needed."""
    version = argv[1] if len(argv) > 1 else metadata.version("grpcio")
    level, message = evaluate(version, today or date.today())
    print(message if level == "ok" else f"::{level}::{message}")
    return 1 if level == "error" else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
