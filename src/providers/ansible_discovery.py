"""Discovery routines for Ansible Vault files and credentials."""

from __future__ import annotations

import os
from typing import Callable, List, Optional


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
    """Detect Ansible Vault password file from environment or workspace.

    Returns:
        Optional[str]: Path to detected password file or None.
    """
    env_file = os.getenv("ANSIBLE_VAULT_PASSWORD_FILE")
    if env_file and os.path.exists(env_file):
        return os.path.abspath(env_file)

    cwd = os.getcwd()
    for cand in (".vault_pass", ".vault_password", "vault.pass", "vault-pass.txt"):
        p = os.path.join(cwd, cand)
        if os.path.exists(p):
            return p

    home_pass = os.path.expanduser("~/.vault_pass")
    if os.path.exists(home_pass):
        return home_pass

    return None


def detect_password(
    detect_file_fn: Optional[Callable[[], Optional[str]]] = None,
) -> Optional[str]:
    """Detect plaintext vault password from environment or password file.

    Args:
        detect_file_fn: Optional function to retrieve password file path.

    Returns:
        Optional[str]: Detected password string or None.
    """
    env_pass = os.getenv("ANSIBLE_VAULT_PASSWORD")
    if env_pass:
        return env_pass

    file_getter = detect_file_fn or detect_password_file
    pass_file = file_getter()
    if pass_file and os.path.exists(pass_file):
        try:
            with open(pass_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
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
                        pass
    except Exception:
        pass
    return sorted(list(set(results)))
