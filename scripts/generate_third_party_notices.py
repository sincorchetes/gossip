#!/usr/bin/env python3
"""Generate THIRD_PARTY_NOTICES.md: licenses and credits of the software Gossip bundles.

The Python part is read from the package metadata of the exact versions pinned (with hashes) in
the lock files, installed into a temporary directory, so it matches what the releases ship. The
native libraries come from packaging/licenses/native-components.json.

Usage: generate_third_party_notices.py [--output FILE] [--site-packages DIR]
Without --site-packages the locked packages are installed into a temporary directory with uv.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
LOCK_FILES = ("requirements-build.txt", "requirements-windows.txt")
# Used only while building; none of them is part of the shipped application.
BUILD_ONLY = {
    "altgraph",
    "macholib",
    "pefile",
    "pyinstaller",
    "pyinstaller-hooks-contrib",
    "pywin32-ctypes",
}
_ENTRY = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)")
_LICENSE_FILE = re.compile(r"(licen[sc]e|copying|notice|copyright)", re.IGNORECASE)
_URL_LABELS = ("homepage", "home", "source", "repository", "documentation")


def normalize(name: str) -> str:
    """PEP 503 normalized package name."""
    return re.sub(r"[-_.]+", "-", name).lower()


@dataclass
class Package:
    """License information collected for one Python package.

    Attributes:
        name: Distribution name.
        version: Pinned version.
        license: SPDX expression or the best description available.
        url: Project home page.
        texts: (file name, content) of the license files shipped with the package.
    """

    name: str
    version: str
    license: str
    url: str = ""
    texts: List[Tuple[str, str]] = field(default_factory=list)


def locked_packages(paths: Iterable[Path]) -> Dict[str, str]:
    """Return {normalized name: version} for every entry of the given lock files."""
    pinned: Dict[str, str] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _ENTRY.match(line)
            if match:
                pinned.setdefault(normalize(match.group(1)), match.group(2))
    return pinned


def license_label(meta: "metadata.PackageMetadata") -> str:
    """Pick the clearest license description from a package's metadata."""
    expression = meta.get("License-Expression")
    if expression:
        return expression.strip()
    text = (meta.get("License") or "").strip()
    if text and "\n" not in text and len(text) <= 80 and text.upper() != "UNKNOWN":
        return text
    classifiers = [
        c.rsplit("::", 1)[-1].strip()
        for c in meta.get_all("Classifier") or []
        if c.startswith("License ::") and not c.endswith("OSI Approved")
    ]
    if classifiers:
        return " / ".join(classifiers)
    return "see license text"


def project_url(meta: "metadata.PackageMetadata") -> str:
    """Pick the project home page from a package's metadata."""
    urls = {}
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        urls.setdefault(label.strip().lower(), url.strip())
    for label in _URL_LABELS:
        if urls.get(label):
            return urls[label]
    return meta.get("Home-page") or next(iter(urls.values()), "")


def read_license_files(dist: "metadata.Distribution") -> List[Tuple[str, str]]:
    """Return the license-like files shipped inside a distribution."""
    found: List[Tuple[str, str]] = []
    for file in dist.files or []:
        if not _LICENSE_FILE.search(file.name) or file.suffix in {".py", ".pyc", ".json"}:
            continue
        try:
            text = Path(dist.locate_file(file)).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if text.strip():
            found.append((file.name, text.strip()))
    return found


def collect_packages(
    pinned: Dict[str, str], distributions: Iterable["metadata.Distribution"]
) -> Tuple[List[Package], List[str]]:
    """Describe every shipped package found among the installed distributions.

    Args:
        pinned: {normalized name: version} from the lock files.
        distributions: Installed distributions to read metadata from.

    Returns:
        Tuple[List[Package], List[str]]: The packages (sorted) and the names not found.
    """
    by_name = {normalize(d.metadata["Name"]): d for d in distributions if d.metadata["Name"]}
    packages: List[Package] = []
    missing: List[str] = []
    for name, version in sorted(pinned.items()):
        if name in BUILD_ONLY:
            continue
        dist = by_name.get(name)
        if dist is None:
            missing.append(name)
            continue
        packages.append(
            Package(
                name=dist.metadata["Name"],
                version=version,
                license=license_label(dist.metadata),
                url=project_url(dist.metadata),
                texts=read_license_files(dist),
            )
        )
    return packages, missing


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def group_texts(packages: Sequence[Package]) -> List[Tuple[str, str, List[str]]]:
    """Group identical license texts so each distinct text is printed once.

    Returns:
        List[Tuple[str, str, List[str]]]: (title, text, packages using it), most used first.
    """
    groups: Dict[str, Dict[str, object]] = {}
    for package in packages:
        for _name, text in package.texts:
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()
            entry = groups.setdefault(
                key, {"text": text, "licenses": defaultdict(int), "users": []}
            )
            entry["licenses"][package.license] += 1  # type: ignore[index]
            if package.name not in entry["users"]:  # type: ignore[operator]
                entry["users"].append(package.name)  # type: ignore[union-attr]
    ordered = sorted(groups.values(), key=lambda e: (-len(e["users"]), e["text"]))  # type: ignore[arg-type]
    result = []
    for entry in ordered:
        licenses = entry["licenses"]
        title = max(licenses, key=lambda k: (licenses[k], k))  # type: ignore[arg-type,index]
        result.append((title, str(entry["text"]), sorted(entry["users"], key=str.lower)))  # type: ignore[arg-type]
    return result


def render(
    packages: Sequence[Package],
    natives: Sequence[Dict[str, str]],
    reference_texts: Sequence[Tuple[str, str]],
) -> str:
    """Render the notices document.

    Args:
        packages: Python packages with their license data.
        natives: Native components (name, license, url, optional note).
        reference_texts: (title, text) license texts for the native components.

    Returns:
        str: Markdown document.
    """
    out: List[str] = [
        "# Third-party notices",
        "",
        "Gossip is licensed under the GNU General Public License, version 3 or (at your option) "
        "any later version (see `LICENSE`). Its packages bundle the third-party software listed "
        "below, each distributed under its own license. This file is generated by "
        "`scripts/generate_third_party_notices.py`; do not edit it by hand.",
        "",
        "## Native libraries, runtimes and resources",
        "",
        "| Component | License | Source |",
        "|---|---|---|",
    ]
    for item in natives:
        out.append(f"| {_cell(item['name'])} | {_cell(item['license'])} | {item['url']} |")
    notes = [item["note"] for item in natives if item.get("note")]
    out += ["", *notes] if notes else []
    out += [
        "",
        "The packages also contain the transitive C libraries these depend on (image, font, "
        "compression, XML, TLS and X11 libraries, among others). Each keeps its own license: the "
        "license files of the libraries bundled in a given package are shipped with it in the "
        "`licenses/` folder. Libraries under the LGPL are distributed as separate shared "
        "libraries, so you can replace them with your own builds; their source code is "
        "available from the project sites above.",
        "",
        "## Python packages",
        "",
        "| Package | Version | License | Project |",
        "|---|---|---|---|",
    ]
    for p in packages:
        out.append(f"| {_cell(p.name)} | {p.version} | {_cell(p.license)} | {p.url} |")

    out += ["", "## License texts of the Python packages", ""]
    for index, (title, text, users) in enumerate(group_texts(packages), start=1):
        out += [
            f"### {index}. {title}",
            "",
            f"Used by: {', '.join(users)}",
            "",
            "```text",
            text,
            "```",
            "",
        ]

    out += ["## License texts of the native components", ""]
    for title, text in reference_texts:
        out += [f"### {title}", "", "```text", text.strip(), "```", ""]
    return "\n".join(out).rstrip() + "\n"


def install_locked(target: Path) -> None:
    """Install the locked packages (with hash checking) into a plain directory."""
    for name in LOCK_FILES:
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--no-deps",
                "--require-hashes",
                "--target",
                str(target),
                "-r",
                str(ROOT / name),
            ],
            check=True,
            capture_output=True,
        )


def build(site_packages: Optional[Path]) -> str:
    """Build the notices text, installing the locked packages first when no directory is given."""
    pinned = locked_packages(ROOT / name for name in LOCK_FILES)
    natives = json.loads((ROOT / "packaging/licenses/native-components.json").read_text())[
        "components"
    ]
    reference = [
        (
            "GNU Lesser General Public License, version 2.1",
            (ROOT / "packaging/licenses/LGPL-2.1.txt").read_text(),
        ),
        (
            "Python Software Foundation License, version 2",
            (ROOT / "packaging/licenses/PSF-2.0.txt").read_text(),
        ),
    ]

    def read(path: Path) -> str:
        packages, missing = collect_packages(pinned, metadata.distributions(path=[str(path)]))
        if missing:
            raise SystemExit(f"Packages without metadata: {', '.join(missing)}")
        return render(packages, natives, reference)

    if site_packages is not None:
        return read(site_packages)
    with tempfile.TemporaryDirectory() as tmp:
        install_locked(Path(tmp))
        return read(Path(tmp))


def main(argv: List[str]) -> int:
    """Generate the notices file."""
    parser = argparse.ArgumentParser(description="Generate THIRD_PARTY_NOTICES.md")
    parser.add_argument("--output", type=Path, default=ROOT / "THIRD_PARTY_NOTICES.md")
    parser.add_argument("--site-packages", type=Path, default=None)
    args = parser.parse_args(argv[1:])
    args.output.write_text(build(args.site_packages), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
