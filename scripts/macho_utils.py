"""Mach-O inspection and library-seeding helpers used by bundle_macos.py."""

from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
from pathlib import Path


def stamp_bundle_version(app_path: Path, version: str) -> None:
    """Write the release version into the bundle's Info.plist.

    PyInstaller leaves 0.0.0 there. macOS refreshes the cached icon and metadata of an app
    when its version changes, so a stale icon from an earlier install does not stay forever.

    Args:
        app_path: The ``.app`` directory.
        version: Version such as ``0.3.69`` (a leading ``v`` is removed).
    """
    version = version.lstrip("v")
    plist_path = app_path / "Contents" / "Info.plist"
    with plist_path.open("rb") as fh:
        info = plistlib.load(fh)
    info["CFBundleShortVersionString"] = version
    info["CFBundleVersion"] = version
    with plist_path.open("wb") as fh:
        plistlib.dump(info, fh)


def is_macho(path: Path) -> bool:
    """Check if file is a Mach-O binary (executable, dylib, bundle)."""
    if not path.is_file() or path.is_symlink():
        return False
    try:
        with open(path, "rb") as f:
            magic = f.read(4)
        return magic in (
            b"\xca\xfe\xba\xbe",  # Universal Fat Binary (BE)
            b"\xbe\xba\xfe\xca",  # Universal Fat Binary (LE)
            b"\xfe\xed\xfa\xce",  # Mach-O 32-bit (BE)
            b"\xce\xfa\xed\xfe",  # Mach-O 32-bit (LE)
            b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit (BE)
            b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit (LE)
        )
    except Exception:
        return False


def get_dependencies(path: Path) -> list[str]:
    """Get list of dylib dependencies from otool -L."""
    try:
        out = subprocess.check_output(["otool", "-L", str(path)], text=True)
    except Exception:
        return []
    deps = []
    lines = out.strip().split("\n")
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\S+)", line)
        if match:
            dep = match.group(1)
            deps.append(dep)
    return deps


def get_rpaths(path: Path) -> list[str]:
    """Get list of existing LC_RPATHs for a binary."""
    try:
        out = subprocess.check_output(["otool", "-l", str(path)], text=True)
    except Exception:
        return []
    rpaths = []
    lines = out.split("\n")
    for i, line in enumerate(lines):
        if "cmd LC_RPATH" in line:
            for next_line in lines[i : i + 5]:
                if "path " in next_line:
                    match = re.search(r"path\s+(\S+)", next_line)
                    if match:
                        rpaths.append(match.group(1))
                    break
    return rpaths


def is_system_lib(dep: str) -> bool:
    """Check if library is a macOS system library."""
    return (
        dep.startswith("/usr/lib/")
        or dep.startswith("/System/Library/")
        or dep.startswith("/System/Volumes/")
    )


def copy_lib_with_symlinks(src_path: Path, dst_dir: Path) -> list[Path]:
    """Copy library and any related symlinks/names to destination directory."""
    copied: list[Path] = []
    real_src = src_path.resolve()
    if not real_src.is_file():
        return copied

    # Copy real binary
    dst_real = dst_dir / real_src.name
    if not dst_real.exists():
        shutil.copy2(real_src, dst_real)
        os.chmod(dst_real, 0o755)
        copied.append(dst_real)

    # If src_path is a symlink or has a different name, create symlink
    if src_path.name != real_src.name:
        dst_link = dst_dir / src_path.name
        if not dst_link.exists():
            try:
                dst_link.symlink_to(real_src.name)
            except Exception:
                shutil.copy2(real_src, dst_link)
                os.chmod(dst_link, 0o755)
                copied.append(dst_link)

    return copied


def seed_homebrew_libraries(brew_prefix: Path, frameworks_dir: Path) -> list[Path]:
    """Copy essential GTK4, Libadwaita and core libraries into Frameworks."""
    lib_dir = brew_prefix / "lib"
    if not lib_dir.is_dir():
        return []

    essential_patterns = [
        "libgtk-4*.dylib",
        "libadwaita-1*.dylib",
        "libgirepository-*.dylib",
        "libgio-*.dylib",
        "libglib-*.dylib",
        "libgobject-*.dylib",
        "libgmodule-*.dylib",
        "libcairo*.dylib",
        "libpango*.dylib",
        "libharfbuzz*.dylib",
        "libgdk_pixbuf*.dylib",
        "librsvg*.dylib",
        "libgraphene*.dylib",
        "libepoxy*.dylib",
        "libintl*.dylib",
        "libffi*.dylib",
    ]

    copied: list[Path] = []
    for pat in essential_patterns:
        for match in lib_dir.glob(pat):
            copied.extend(copy_lib_with_symlinks(match, frameworks_dir))
    return copied


def seed_openssl(brew_prefix: Path, frameworks_dir: Path) -> list[Path]:
    """Force Homebrew's OpenSSL into Frameworks, replacing any older copy already collected.

    PyInstaller may have placed its own libssl/libcrypto there; cryptography's Rust bindings
    need symbols (e.g. SSL_get0_group_name, OpenSSL >= 3.2) that older copies lack.
    """
    lib_dir = brew_prefix / "opt" / "openssl@3" / "lib"
    if not lib_dir.is_dir():
        return []

    copied: list[Path] = []
    for pat in ("libssl*.dylib", "libcrypto*.dylib"):
        for match in lib_dir.glob(pat):
            for stale in (frameworks_dir / match.name, frameworks_dir / match.resolve().name):
                if stale.is_symlink() or stale.exists():
                    stale.unlink()
            copied.extend(copy_lib_with_symlinks(match, frameworks_dir))
    return copied


def resolve_dependency_source(dep: str, brew_prefix: Path) -> Path | None:
    """Quickly locate source file for a dependency without expensive deep recursive search."""
    dep_path = Path(dep)
    if dep_path.is_absolute() and dep_path.is_file():
        return dep_path.resolve()

    # Check directly in brew_prefix / lib
    cand = brew_prefix / "lib" / dep_path.name
    if cand.is_file():
        return cand.resolve()

    # Check 1 level inside brew_prefix / opt / */lib
    opt_dir = brew_prefix / "opt"
    if opt_dir.is_dir():
        for opt_pkg in opt_dir.iterdir():
            opt_cand = opt_pkg / "lib" / dep_path.name
            if opt_cand.is_file():
                return opt_cand.resolve()

    return None


_LICENSE_FILE_PATTERNS = ("LICENSE*", "LICENCE*", "COPYING*", "COPYRIGHT*", "NOTICE*", "AUTHORS*")


def formula_directory(source: Path) -> Path | None:
    """Return the Homebrew Cellar directory of the formula that installed a library.

    Args:
        source: Resolved path of a library inside the Cellar.

    Returns:
        The `.../Cellar/<formula>/<version>` directory, or None if the file is not in the Cellar.
    """
    parts = source.parts
    if "Cellar" not in parts:
        return None
    index = parts.index("Cellar")
    if len(parts) < index + 3:
        return None
    return Path(*parts[: index + 3])


def collect_license_files(frameworks_dir: Path, brew_prefix: Path, licenses_dir: Path) -> list[str]:
    """Copy the license files of every Homebrew formula whose libraries were bundled.

    Args:
        frameworks_dir: The app's Contents/Frameworks directory.
        brew_prefix: Homebrew prefix the libraries were copied from.
        licenses_dir: Destination (one sub-folder per formula).

    Returns:
        list[str]: Names of the formulae whose license files were copied.
    """
    formulae: dict[str, Path] = {}
    for item in sorted(frameworks_dir.iterdir()):
        if item.is_dir():
            continue
        source = resolve_dependency_source(item.name, brew_prefix)
        directory = formula_directory(source) if source else None
        if directory is not None:
            formulae.setdefault(directory.parent.name, directory)

    copied: list[str] = []
    for name, directory in sorted(formulae.items()):
        files = {
            f for pattern in _LICENSE_FILE_PATTERNS for f in directory.glob(pattern) if f.is_file()
        }
        if not files:
            continue
        target = licenses_dir / name
        target.mkdir(parents=True, exist_ok=True)
        for file in sorted(files):
            shutil.copy2(file, target / file.name)
        copied.append(name)
    return copied
