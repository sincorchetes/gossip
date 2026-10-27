"""Discovery routines for Ansible Vault files and credentials."""

from __future__ import annotations

import os
import stat
import sys
from typing import Callable, List, Optional

from src.i18n import _
from src.log import get_logger

log = get_logger(__name__)


def detect_vault_file() -> Optional[str]:
    """Detect active Ansible Vault file from environment variables or workspace.

    Returns:
        Optional[str]: Path to detected vault file or None.
    """
    env_val = os.getenv("ANSIBLE_VAULT_FILE")
    if env_val and os.path.exists(env_val):
        return os.path.abspath(env_val)

    candidates = [
        "vault.yml",
        "vault.yaml",
        "group_vars/all/vault.yml",
        "group_vars/all/vault.yaml",
        "vars/vault.yml",
        "vars/vault.yaml",
        "secrets.yml",
        "secrets.yaml",
        ".vault.yml",
    ]
    cwd = os.getcwd()
    for cand in candidates:
        p = os.path.join(cwd, cand)
        if os.path.exists(p):
            return p
    return None


def detect_password_file() -> Optional[str]:
    """Detect the Ansible Vault password file declared explicitly by the user.

    Only ANSIBLE_VAULT_PASSWORD_FILE is honoured; password files are never guessed from the
    working directory or home folder, so a stray plaintext file cannot unlock a vault silently.

    Returns:
        Optional[str]: Path to the declared password file or None.
    """
    env_file = os.getenv("ANSIBLE_VAULT_PASSWORD_FILE")
    if env_file and os.path.exists(env_file):
        return os.path.abspath(env_file)
    return None


def is_password_file_private(path: str) -> bool:
    """Check that a password file is not accessible to group or other users.

    Args:
        path: Filesystem path of the password file.

    Returns:
        bool: True if only the owner can access it (always True on Windows).
    """
    if sys.platform == "win32":
        return True
    try:
        return stat.S_IMODE(os.stat(path).st_mode) & 0o077 == 0
    except OSError:
        return False


def read_password_file(path: str) -> Optional[str]:
    """Read a vault password from a file, refusing files readable by other users.

    Args:
        path: Filesystem path of the password file.

    Returns:
        Optional[str]: The stripped password, or None if missing, unreadable or too permissive.
    """
    if not os.path.exists(path):
        return None
    if not is_password_file_private(path):
        print(
            _(
                "Ignoring password file '{path}': it is accessible to other users. "
                "Run: chmod 600 '{path}'"
            ).format(path=path),
            file=sys.stderr,
        )
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None


def detect_password(
    detect_file_fn: Optional[Callable[[], Optional[str]]] = None,
) -> Optional[str]:
    """Read the vault password from the explicitly declared password file.

    The password itself is never taken from the environment (other processes of the same user
    can read it); it is either typed in the unlock dialog or read from a private file.

    Args:
        detect_file_fn: Optional function to retrieve password file path.

    Returns:
        Optional[str]: Password read from the file, or None.
    """
    file_getter = detect_file_fn or detect_password_file
    pass_file = file_getter()
    if pass_file:
        return read_password_file(pass_file)
    return None


def find_local_vault_files() -> List[str]:
    """Scan current workspace directory for Ansible Vault encrypted files.

    Returns:
        List[str]: Discovered encrypted file paths.
    """
    results: List[str] = []
    cwd = os.getcwd()
    try:
        for root, dirs, files in os.walk(cwd):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")
            ]
            for f in files:
                if f.endswith((".yml", ".yaml", ".vault")):
                    full_path = os.path.join(root, f)
                    try:
                        with open(full_path, "rb") as fp:
                            header = fp.read(30)
                            if header.startswith(b"$ANSIBLE_VAULT"):
                                results.append(full_path)
                            elif "vault" in f.lower():
                                results.append(full_path)
                    except Exception:
                        log.debug("unreadable file while scanning for vaults", exc_info=True)
    except Exception:
        log.debug("workspace vault scan failed", exc_info=True)
    return sorted(list(set(results)))
