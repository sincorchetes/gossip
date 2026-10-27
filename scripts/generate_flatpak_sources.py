#!/usr/bin/env python3
"""Write the Flatpak module that installs Gossip's Python dependencies offline.

Flatpak builds have no network, so every dependency must be a source with a URL and a SHA-256.
This reads the hashed release lock (requirements-build.txt), asks PyPI where each pinned file
lives, and keeps only files whose hash is in the lock, so the Flatpak installs exactly what the
other packages do. Wheels are chosen per architecture; pure-Python ones are shared.

Usage:
    generate_flatpak_sources.py [--lock requirements-build.txt] [--python 314]
                                [--output packaging/flatpak/python3-deps.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pip_lock_subset import normalize, parse_lock  # noqa: E402

ARCHES = ("x86_64", "aarch64")
# Needed to build or package Gossip elsewhere, not to run it inside Flatpak
SKIPPED = {
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "altgraph",
    "macholib",
    "pefile",
    "pywin32-ctypes",
    "setuptools",
}
_WHEEL = re.compile(
    r"^(?P<name>.+?)-(?P<version>[^-]+)(?:-(?P<build>\d[^-]*))?-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>[^-]+)\.whl$"
)
_MANYLINUX = re.compile(r"^manylinux(?:_(\d+)_(\d+)|2014|2010|1)_(x86_64|aarch64)$")
GLIBC_MAX = (2, 44)  # glibc of the GNOME 51 runtime


def _applies_to_linux(entry_line: str) -> bool:
    """False for entries restricted to macOS or Windows by an environment marker."""
    marker = entry_line.partition(";")[2]
    return not marker or ("darwin" not in marker and "win32" not in marker) or "linux" in marker


def parse_requirement(line: str) -> Tuple[str, str]:
    """Return (normalized name, version) of a ``name==version ...`` lock line."""
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)", line)
    if not match:
        raise ValueError(f"not a pinned requirement: {line!r}")
    return normalize(match.group(1)), match.group(2)


def wheel_arch(filename: str, python: str) -> Optional[str]:
    """Which architecture a wheel serves: 'any', 'x86_64', 'aarch64', or None if unusable.

    Args:
        filename: Wheel file name.
        python: Interpreter tag digits of the runtime, e.g. ``314``.
    """
    match = _WHEEL.match(filename)
    if not match:
        return None
    py_tags = match["py"].split(".")
    abi, plat = match["abi"], match["plat"]
    wanted = f"cp{python}"
    minor = int(python[1:]) if len(python) > 1 else 0

    def python_ok() -> bool:
        for tag in py_tags:
            if tag in ("py3", "py2", "py30") or re.fullmatch(r"py3\d*", tag):
                return abi == "none"
            if tag == wanted and abi in (wanted, "abi3", "none"):
                return True
            if re.fullmatch(r"cp3\d+", tag) and abi == "abi3" and int(tag[3:]) <= minor:
                return True
        return False

    if not python_ok():
        return None
    if plat == "any":
        return "any"
    for part in plat.split("."):
        found = _MANYLINUX.match(part)
        if found:
            if found[1] and (int(found[1]), int(found[2])) > GLIBC_MAX:
                continue
            return found[3]
    return None


def pick_files(files: Iterable[Dict[str, Any]], python: str) -> Dict[str, Dict[str, Any]]:
    """Choose, per architecture ('any' or each of ARCHES), one wheel from a PyPI file list."""
    chosen: Dict[str, Dict[str, Any]] = {}
    for item in sorted(files, key=lambda f: f["filename"]):
        if item.get("packagetype") != "bdist_wheel" or item.get("yanked"):
            continue
        arch = wheel_arch(item["filename"], python)
        if arch and arch not in chosen:
            chosen[arch] = item
    return chosen


def fetch_files(name: str, version: str) -> List[Dict[str, Any]]:
    """Ask PyPI for the files of one release."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=60) as resp:
        return json.load(resp)["urls"]


def build_module(lock_text: str, python: str, fetch=fetch_files) -> Dict[str, Any]:
    """Build the Flatpak module for every Linux-relevant package of the lock.

    Raises:
        SystemExit: If a package has no usable wheel or its files are not in the lock.
    """
    sources: List[Dict[str, Any]] = []
    problems: List[str] = []
    for name, lines in parse_lock(lock_text):
        if name in SKIPPED or not _applies_to_linux(lines[0]):
            continue
        _name, version = parse_requirement(lines[0])
        locked = {
            line.split("sha256:")[1].split()[0].rstrip("\\")
            for line in lines[1:]
            if "sha256:" in line
        }
        chosen = pick_files(fetch(name, version), python)
        if "any" in chosen:
            picks = [("any", chosen["any"])]
        else:
            picks = [(arch, chosen[arch]) for arch in ARCHES if arch in chosen]
            missing = [arch for arch in ARCHES if arch not in chosen]
            if missing:
                problems.append(f"{name}=={version}: no cp{python} wheel for {', '.join(missing)}")
        for arch, item in picks:
            digest = item["digests"]["sha256"]
            if digest not in locked:
                problems.append(f"{item['filename']}: not in the lock (hash {digest[:12]}…)")
                continue
            source: Dict[str, Any] = {"type": "file", "url": item["url"], "sha256": digest}
            if arch != "any":
                source["only-arches"] = [arch]
            sources.append(source)
    if problems:
        raise SystemExit("Cannot build the Flatpak sources:\n  " + "\n  ".join(problems))
    sources.sort(key=lambda s: (s["url"].rsplit("/", 1)[1].lower(), s.get("only-arches", [""])[0]))
    return {
        "name": "python3-deps",
        "buildsystem": "simple",
        "build-commands": [
            'pip3 install --verbose --exists-action=i --no-index --find-links="file://${PWD}" '
            "--prefix=${FLATPAK_DEST} --no-deps --no-build-isolation *.whl"
        ],
        "sources": sources,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", default="requirements-build.txt")
    parser.add_argument("--python", default="314", help="runtime Python tag digits (default 314)")
    parser.add_argument("--output", default="packaging/flatpak/python3-deps.json")
    args = parser.parse_args(argv)
    module = build_module(Path(args.lock).read_text(encoding="utf-8"), args.python)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(module, indent=2) + "\n", encoding="utf-8")
    print(f"{len(module['sources'])} sources written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
