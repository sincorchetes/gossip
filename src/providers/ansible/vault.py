"""Low-level file encryption, decryption, and serialization for Ansible Vault."""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable, Dict, Optional, Tuple

import yaml
from ansible.parsing.vault import AnsibleVaultError, VaultLib, VaultSecret

from src.i18n import _


def get_vault_lib(password: str, vault_id: str = "default") -> VaultLib:
    """Construct an Ansible VaultLib instance with the provided plaintext password.

    Args:
        password: Plaintext decryption password.
        vault_id: Ansible Vault identifier string.

    Returns:
        VaultLib: Configured vault encryption/decryption library instance.
    """
    secret = VaultSecret(password.encode("utf-8"))
    return VaultLib([(vault_id or "default", secret)])


def parse_vault_payload(text: str) -> Any:
    """Smart parser for user payload string, parsing JSON/YAML or preserving string.

    Args:
        text: User-entered raw payload string.

    Returns:
        Any: Parsed dictionary/list or original string.
    """
    stripped = text.strip()
    if stripped.startswith(("{", "[")) or stripped in ("true", "false", "yes", "no"):
        try:
            return yaml.safe_load(stripped)
        except Exception:
            pass
    return text


def load_vault_data(
    vault_file: str,
    password: Optional[str],
    vault_id: str = "default",
    vault_lib_getter: Optional[Callable[[], VaultLib]] = None,
) -> Dict[str, Any]:
    """Read and decrypt an Ansible Vault YAML file.

    Args:
        vault_file: Filesystem path to the vault file.
        password: Optional decryption password.
        vault_id: Vault ID string.
        vault_lib_getter: Optional custom VaultLib supplier.

    Returns:
        Dict[str, Any]: Decrypted dictionary contents.

    Raises:
        FileNotFoundError: If the target vault file is missing.
        PermissionError: If the password is missing or invalid.
        RuntimeError: If decryption fails or YAML syntax is invalid.
    """
    if not os.path.exists(vault_file):
        raise FileNotFoundError(
            _("The Ansible Vault file '{path}' does not exist.").format(path=vault_file)
        )

    with open(vault_file, "rb") as f:
        raw_bytes = f.read()

    if not raw_bytes.strip():
        return {}

    if raw_bytes.startswith(b"$ANSIBLE_VAULT"):
        if not password and not vault_lib_getter:
            raise PermissionError(
                _(
                    "No password provided to unlock Ansible Vault.\n"
                    "Enter password or select your .vault_pass file."
                )
            )

        try:
            vault_lib = (
                vault_lib_getter() if vault_lib_getter else get_vault_lib(password or "", vault_id)
            )
            plaintext_bytes = vault_lib.decrypt(raw_bytes)
            plaintext = plaintext_bytes.decode("utf-8")
        except AnsibleVaultError as exc:
            raise PermissionError(
                _(
                    "Incorrect password or failed to decrypt Ansible Vault '{filename}'.\n"
                    "Detail: {detail}"
                ).format(filename=os.path.basename(vault_file), detail=exc)
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"{_('Error decrypting Ansible Vault')}: {exc}") from exc
    else:
        plaintext = raw_bytes.decode("utf-8", errors="replace")

    try:
        parsed = yaml.safe_load(plaintext)
        if parsed is None:
            parsed = {}
        elif not isinstance(parsed, dict):
            parsed = {"content": parsed}
    except Exception as exc:
        raise RuntimeError(
            _("Decrypted content of '{filename}' is not valid YAML: {detail}").format(
                filename=os.path.basename(vault_file), detail=exc
            )
        ) from exc

    return parsed


def save_vault_data(
    vault_file: str,
    data: Dict[str, Any],
    password: str,
    vault_id: str = "default",
    vault_lib_getter: Optional[Callable[[], VaultLib]] = None,
) -> None:
    """Serializes dictionary to YAML, encrypts with VaultLib, and writes atomically.

    Args:
        vault_file: Target filesystem path for the vault file.
        data: Python dictionary of variables to store.
        password: Plaintext password used for encryption.
        vault_id: Vault identifier string.
        vault_lib_getter: Optional custom VaultLib supplier.
    """
    os.makedirs(os.path.dirname(os.path.abspath(vault_file)), exist_ok=True)

    if os.path.exists(vault_file):
        bak_path = f"{vault_file}.bak"
        try:
            shutil.copy2(vault_file, bak_path)
        except Exception:
            pass

    yaml_str = yaml.dump(data, sort_keys=True, allow_unicode=True, default_flow_style=False)
    vault_lib = vault_lib_getter() if vault_lib_getter else get_vault_lib(password, vault_id)
    encrypted_bytes = vault_lib.encrypt(yaml_str.encode("utf-8"))

    temp_path = f"{vault_file}.tmp"
    with open(temp_path, "wb") as f:
        f.write(encrypted_bytes)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, vault_file)


def read_backup_payload(
    vault_file: str,
    key: str,
    password: str,
    vault_id: str = "default",
    vault_lib_getter: Optional[Callable[[], VaultLib]] = None,
) -> Optional[Tuple[str, bool]]:
    """Fetch variable payload from a backup (.bak) vault file.

    Args:
        vault_file: Path to active vault file whose .bak will be read.
        key: Variable key to retrieve.
        password: Plaintext password to decrypt the backup file.
        vault_id: Vault ID string.

    Returns:
        Optional[Tuple[str, bool]]: Payload string representation and is_binary flag if found, or None.

    Raises:
        RuntimeError: If reading or decrypting an existing backup file fails.
    """
    bak_file = f"{vault_file}.bak"
    if not os.path.exists(bak_file):
        return None

    try:
        with open(bak_file, "rb") as f:
            bak_bytes = f.read()
        vault_lib = vault_lib_getter() if vault_lib_getter else get_vault_lib(password, vault_id)
        bak_plain = vault_lib.decrypt(bak_bytes).decode("utf-8")
        bak_data = yaml.safe_load(bak_plain) or {}
        if key in bak_data:
            val = bak_data[key]
            if isinstance(val, (dict, list)):
                return yaml.dump(val, sort_keys=False, default_flow_style=False), False
            return str(val), False
        return None
    except Exception as exc:
        raise RuntimeError(f"{_('Could not read backup version')}: {exc}") from exc
