#!/usr/bin/env python3
"""Convert the Markdown license text into the RTF file the Windows installer displays.

Usage: make_license_rtf.py <LICENSE.md> <output.rtf>
"""

from __future__ import annotations

import sys
from pathlib import Path


def _escape(line: str) -> str:
    """Escape one line for RTF (control characters and non-ASCII code points)."""
    out = []
    for char in line:
        code = ord(char)
        if char in "\\{}":
            out.append("\\" + char)
        elif char == "\t":
            out.append("\\tab ")
        elif code > 126:
            signed = code - 0x10000 if code > 0x7FFF else code
            out.append(f"\\u{signed}?")
        else:
            out.append(char)
    return "".join(out)


def markdown_to_rtf(text: str) -> str:
    """Render the license as monospaced RTF, dropping Markdown headings and code fences.

    Args:
        text: Contents of LICENSE.md.

    Returns:
        str: A complete RTF document.
    """
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            continue
        lines.append(_escape(raw.lstrip("# ").rstrip() if raw.startswith("#") else raw.rstrip()))
    body = "\\par\n".join(lines)
    return (
        "{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0\\fmodern Courier New;}}\\f0\\fs18\n"
        + body
        + "\\par\n}\n"
    )


def main(argv: list[str]) -> int:
    """Read the Markdown license and write the RTF version."""
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    source, target = Path(argv[1]), Path(argv[2])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown_to_rtf(source.read_text(encoding="utf-8")), encoding="ascii")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
