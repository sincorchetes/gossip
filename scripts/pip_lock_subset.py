#!/usr/bin/env python3
"""Print the entries of a hashed requirements lock that are not already installed.

The Windows build gets its native packages from MSYS2 (pacman) and everything else from PyPI.
This keeps hash checking for the PyPI part: the output is a valid requirements file (with its
``--hash`` lines) that can be installed with ``pip install --no-deps --require-hashes -r``.

Usage: pip_lock_subset.py <requirements-lock.txt> <pip-freeze-of-installed-packages.txt> [--skip NAME ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, Iterator, List, Set, Tuple

_ENTRY = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==")


def normalize(name: str) -> str:
    """Return the PEP 503 normalized form of a package name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_lock(text: str) -> Iterator[Tuple[str, List[str]]]:
    """Split a ``uv pip compile --generate-hashes`` lock into (name, lines) entries.

    Args:
        text: Contents of the lock file.

    Yields:
        Tuple[str, List[str]]: Normalized package name and the entry's requirement and
        ``--hash`` lines (comments dropped).
    """
    name = None
    lines: List[str] = []
    for raw in text.splitlines():
        match = _ENTRY.match(raw)
        if match:
            if name is not None:
                yield name, lines
            name, lines = normalize(match.group(1)), [raw.rstrip()]
        elif name is not None and raw.strip().startswith("--hash="):
            lines.append(raw.rstrip())
    if name is not None:
        yield name, lines


def installed_names(freeze_text: str) -> Set[str]:
    """Return the normalized names found in ``pip freeze`` / ``pip list --format=freeze`` output."""
    names = set()
    for raw in freeze_text.splitlines():
        match = _ENTRY.match(raw.strip())
        if match:
            names.add(normalize(match.group(1)))
    return names


def subset(lock_text: str, freeze_text: str, skip: Iterable[str] = ()) -> str:
    """Return the lock entries whose package is not in the freeze output.

    Args:
        lock_text: Hashed requirements lock.
        freeze_text: Output of ``pip list --format=freeze``.
        skip: Package names to leave out even though they are missing.

    Returns:
        str: A requirements file with the missing packages and their hashes.
    """
    present = installed_names(freeze_text) | {normalize(name) for name in skip}
    out: List[str] = []
    for name, lines in parse_lock(lock_text):
        if name not in present:
            out.extend(lines)
    return "\n".join(out) + ("\n" if out else "")


def main(argv: List[str]) -> int:
    """Read the lock and the installed list from files and print the missing entries."""
    if len(argv) < 3 or (len(argv) > 3 and argv[3] != "--skip"):
        print(__doc__, file=sys.stderr)
        return 2
    skipped = argv[4:] if len(argv) > 3 else []
    sys.stdout.write(subset(Path(argv[1]).read_text(), Path(argv[2]).read_text(), skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
