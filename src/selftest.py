"""Headless smoke test that verifies a built package can load all of its native dependencies.

Each module is imported in its own child process so that a native crash (e.g. a segfault while
loading GTK or OpenSSL) is attributed to the module that caused it instead of killing the whole
report.
"""

from __future__ import annotations

import faulthandler
import importlib
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# Modules whose import breaks in frozen bundles when a native library or data file is missing.
_REQUIRED_MODULES: Tuple[str, ...] = (
    "gi",
    "cryptography.hazmat.bindings._rust",
    "yaml",
    "boto3",
    "azure.identity",
    "google.cloud.secretmanager_v1",
    "src.providers",
    "src.ui.app",
)

_CHILD_TIMEOUT_SECONDS = 120

# Functional checks run real code instead of only importing it. Ansible patches parts of the
# standard library only while it is imported, so a working encrypt/decrypt round trip shows
# that the frozen build still runs after those patches were removed.
_FUNCTIONAL_CHECKS: Tuple[str, ...] = ("check:vault-roundtrip",)

# GTK initialises the windowing system when its Python module is imported, which crashes on
# hosts without a display server (e.g. macOS CI runners). In headless mode the UI import is
# replaced by loading the GTK typelibs, which verifies the bundled libraries without opening
# a display connection.
_HEADLESS_ENV = "GOSSIP_SELFTEST_HEADLESS"
_UI_MODULE = "src.ui.app"
_TYPELIB_CHECKS: Tuple[str, ...] = (
    "typelib:Gtk:4.0",
    "typelib:Gdk:4.0",
    "typelib:Adw:1",
    "typelib:Gio:2.0",
    "typelib:GdkPixbuf:2.0",
)


def required_checks() -> Tuple[str, ...]:
    """Return the checks to run, adapting the UI check to headless environments.

    Returns:
        Tuple[str, ...]: Module names and `typelib:<namespace>:<version>` entries.
    """
    if not os.environ.get(_HEADLESS_ENV):
        return _REQUIRED_MODULES + _FUNCTIONAL_CHECKS
    modules = tuple(m for m in _REQUIRED_MODULES if m != _UI_MODULE)
    return modules + _TYPELIB_CHECKS + _FUNCTIONAL_CHECKS


def _vault_roundtrip() -> None:
    """Encrypt and decrypt a value with Ansible Vault, as the app does at runtime."""
    from src.providers.ansible.vault import get_vault_lib

    vault = get_vault_lib("self-test-password")
    if vault.decrypt(vault.encrypt(b"gossip")) != b"gossip":
        raise RuntimeError("decrypted text differs from the original")


_FUNCTIONAL_CHECK_FUNCTIONS = {"vault-roundtrip": _vault_roundtrip}


def check_module(name: str) -> int:
    """Import a single module (runs inside the child process).

    Args:
        name: Dotted module path to import.

    Returns:
        int: 0 on success, 1 if the import raised.
    """
    try:
        faulthandler.enable()
    except (OSError, AttributeError, ValueError, RuntimeError):
        pass  # no usable stderr (e.g. windowed executable); crashes are still reported by exit code
    try:
        if name.startswith("check:"):
            _FUNCTIONAL_CHECK_FUNCTIONS[name.split(":", 1)[1]]()
        elif name.startswith("typelib:"):
            _, namespace, version = name.split(":")
            import gi

            gi.require_version(namespace, version)
        else:
            importlib.import_module(name)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


def _child_command(name: str) -> List[str]:
    """Build the command that re-runs this program to check one module."""
    if getattr(sys, "frozen", False):
        base = [sys.executable]
    else:
        base = [sys.executable, str(Path(__file__).with_name("main.py"))]
    return base + ["--self-test-module", name]


def _describe_failure(proc: subprocess.CompletedProcess) -> str:
    """Summarize why a child check failed, including crash signals and its last output."""
    if proc.returncode < 0:
        reason = f"crashed with signal {-proc.returncode}"
    else:
        reason = f"exit code {proc.returncode}"
    tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
    return reason + ("".join(f"\n    {line}" for line in tail))


def run_self_test() -> int:
    """Check every required module in an isolated child process and report the result.

    Returns:
        int: 0 when all modules import cleanly, 1 otherwise.
    """
    failures: List[str] = []
    checks = required_checks()
    for name in checks:
        try:
            proc = subprocess.run(
                _child_command(name),
                capture_output=True,
                text=True,
                timeout=_CHILD_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{name}: timed out after {_CHILD_TIMEOUT_SECONDS}s")
            continue
        if proc.returncode != 0:
            failures.append(f"{name}: {_describe_failure(proc)}")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    if failures:
        return 1
    print(f"OK: {len(checks)} checks passed")
    return 0
