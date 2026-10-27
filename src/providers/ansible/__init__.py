"""Ansible Vault encrypted YAML file provider package."""

from src.providers.ansible.compat import (
    _MockLibc,
    _MockLibcFunc,
    ansible_import_context,
    ensure_windows_runtime,
)

ensure_windows_runtime()

from src.providers.ansible.client import AnsibleVaultClient
from src.providers.ansible.discovery import (
    detect_password,
    detect_password_file,
    detect_vault_file,
    find_local_vault_files,
)
from src.providers.ansible.vault import (
    get_vault_lib,
    load_vault_data,
    parse_vault_payload,
    read_backup_payload,
    save_vault_data,
)

__all__ = [
    "AnsibleVaultClient",
    "_MockLibc",
    "_MockLibcFunc",
    "detect_password",
    "detect_password_file",
    "detect_vault_file",
    "find_local_vault_files",
    "ansible_import_context",
    "ensure_windows_runtime",
    "get_vault_lib",
    "load_vault_data",
    "parse_vault_payload",
    "read_backup_payload",
    "save_vault_data",
]
