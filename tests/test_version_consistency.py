"""Guard against the version drifting between the places that hold it.

Releases stamp the tag into ``src/__init__.py`` and ``pyproject.toml`` at build time, but the tree
itself (``gossip -v`` from source, the About dialog, ``nix run``) reads these files directly, so
they have to move together when the version is bumped.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _first(pattern: str, relative: str) -> str:
    match = re.search(pattern, (ROOT / relative).read_text(encoding="utf-8"), re.MULTILINE)
    assert match, f"no version found in {relative}"
    return match.group(1)


class TestVersionConsistency(unittest.TestCase):
    def test_all_version_sources_agree(self):
        versions = {
            "src/__init__.py": _first(r'^__version__ = "([^"]+)"', "src/__init__.py"),
            "pyproject.toml": _first(r'^version = "([^"]+)"', "pyproject.toml"),
            "flake.nix": _first(r'^\s*version = "(\d[^"]*)";', "flake.nix"),
            "metainfo (latest release)": _first(
                r'<release version="([^"]+)"',
                "data/com.github.sincorchetes.gossip_gcp.metainfo.xml",
            ),
        }
        self.assertEqual(len(set(versions.values())), 1, f"version mismatch: {versions}")


if __name__ == "__main__":
    unittest.main()
