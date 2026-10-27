#!/usr/bin/env python3
"""Bundle macOS application dependencies into a self-contained .app bundle.

High-performance bundler that collects dynamic libraries (GTK4, Libadwaita,
GdkPixbuf, etc.), rewrites Mach-O install names to relative @rpath references,
and re-signs the application bundle ad-hoc in seconds.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from macho_utils import (
    collect_license_files,
    copy_lib_with_symlinks,
    get_dependencies,
    get_rpaths,
    is_macho,
    is_system_lib,
    resolve_dependency_source,
    seed_homebrew_libraries,
    seed_openssl,
    stamp_bundle_version,
)


def read_source_version(repo_root: Path) -> str:
    """The ``__version__`` of ``src/__init__.py`` (stamped from the tag at release time)."""
    match = re.search(
        r'^__version__ = "([^"]+)"', (repo_root / "src" / "__init__.py").read_text(), re.M
    )
    return match.group(1) if match else ""


def bundle_macos_app(app_path: Path, brew_prefix: Path) -> None:
    """Collect and patch all Mach-O dependencies in the app bundle quickly and deterministically."""
    contents_dir = app_path / "Contents"
    frameworks_dir = contents_dir / "Frameworks"
    frameworks_dir.mkdir(parents=True, exist_ok=True)

    print(f"[*] Seeding essential libraries from Homebrew ({brew_prefix})...")
    seed_homebrew_libraries(brew_prefix, frameworks_dir)
    seed_openssl(brew_prefix, frameworks_dir)

    # Initial set of binaries to inspect (only executable and Frameworks dylibs/sos)
    main_exe = contents_dir / "MacOS" / "gossip"
    binaries: set[Path] = set()
    if main_exe.is_file():
        binaries.add(main_exe)

    for item in frameworks_dir.rglob("*"):
        if is_macho(item):
            binaries.add(item)

    print(f"[*] Inspecting {len(binaries)} initial Mach-O binaries for dependencies...")
    queue = list(binaries)
    scanned: set[Path] = set()

    while queue:
        current = queue.pop(0)
        if current in scanned:
            continue
        scanned.add(current)

        for dep in get_dependencies(current):
            if is_system_lib(dep) or dep.startswith("@rpath/"):
                continue

            dep_name = Path(dep).name
            dst_lib = frameworks_dir / dep_name
            if not dst_lib.exists():
                src_lib = resolve_dependency_source(dep, brew_prefix)
                if src_lib and src_lib.is_file():
                    newly_copied = copy_lib_with_symlinks(src_lib, frameworks_dir)
                    for nc in newly_copied:
                        if is_macho(nc) and nc not in scanned and nc not in queue:
                            queue.append(nc)
                            binaries.add(nc)

    print(f"[*] Patching {len(binaries)} binaries with @rpath install names...")
    bundled_names = {f.name for f in frameworks_dir.iterdir()}

    for binary in binaries:
        try:
            os.chmod(binary, 0o755)
        except Exception:
            pass

        # If inside Frameworks, set ID to @rpath/basename
        if binary.parent == frameworks_dir:
            subprocess.run(
                ["install_name_tool", "-id", f"@rpath/{binary.name}", str(binary)],
                capture_output=True,
            )

        # Rewrite external dependencies to @rpath/basename
        for dep in get_dependencies(binary):
            dep_name = Path(dep).name
            if is_system_lib(dep):
                continue
            if dep_name in bundled_names or not dep.startswith("@"):
                subprocess.run(
                    [
                        "install_name_tool",
                        "-change",
                        dep,
                        f"@rpath/{dep_name}",
                        str(binary),
                    ],
                    capture_output=True,
                )

        # Ensure essential RPATHs are present
        existing_rpaths = get_rpaths(binary)
        target_rpaths = [
            "@executable_path/../Frameworks",
            "@loader_path",
            "@loader_path/..",
            "@loader_path/../Frameworks",
        ]
        for rp in target_rpaths:
            if rp not in existing_rpaths:
                subprocess.run(
                    ["install_name_tool", "-add_rpath", rp, str(binary)],
                    capture_output=True,
                )

    # Ship the licenses of what was bundled; this must happen before the bundle is signed
    resources_dir = contents_dir / "Resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parent.parent
    for notice in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        if (repo_root / notice).is_file():
            shutil.copy2(repo_root / notice, resources_dir / notice)
    formulae = collect_license_files(frameworks_dir, brew_prefix, resources_dir / "licenses")
    print(f"[*] Collected license files of {len(formulae)} Homebrew formulae")

    version = read_source_version(repo_root)
    if version:
        stamp_bundle_version(app_path, version)
        print(f"[*] Stamped bundle version {version}")

    # Re-sign the entire bundle ad-hoc (after every edit: the signature covers Info.plist)
    print("[*] Re-signing application bundle ad-hoc...")
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
        check=True,
    )
    print(f"[+] Bundle complete in seconds: {app_path}")


def main() -> int:
    """Parse CLI arguments and run macOS bundler."""
    parser = argparse.ArgumentParser(description="Bundle macOS .app dependencies.")
    parser.add_argument("app_path", type=Path, help="Path to dist/gossip.app")
    parser.add_argument(
        "--brew-prefix",
        type=Path,
        default=None,
        help="Homebrew prefix (default: detected via brew --prefix)",
    )
    args = parser.parse_args()

    app_path = args.app_path.resolve()
    if not app_path.is_dir():
        print(f"Error: {app_path} does not exist", file=sys.stderr)
        return 1

    brew_prefix = args.brew_prefix
    if brew_prefix is None:
        try:
            detected = subprocess.check_output(["brew", "--prefix"], text=True).strip()
            brew_prefix = Path(detected)
        except Exception:
            brew_prefix = (
                Path("/usr/local") if Path("/usr/local").is_dir() else Path("/opt/homebrew")
            )

    bundle_macos_app(app_path, brew_prefix)
    return 0


if __name__ == "__main__":
    sys.exit(main())
