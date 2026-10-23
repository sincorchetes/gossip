"""Ansible Vault encrypted YAML file provider package."""

from src.providers.ansible.client import AnsibleVaultClient
from src.providers.ansible.compat import (
    _MockLibc,
    _MockLibcFunc,
    install_posix_shims,
)
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
    "get_vault_lib",
    "install_posix_shims",
    "load_vault_data",
    "parse_vault_payload",
    "read_backup_payload",
    "save_vault_data",
]
