"""Low-level file encryption, decryption, and serialization for Ansible Vault."""

from __future__ import annotations

import os
import shutil
import stat
from typing import Any, Callable, Dict, List, Optional, Tuple

import yaml

from src.providers.ansible.compat import ansible_import_context

with ansible_import_context():
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


def _yaml_error_location(exc: Exception) -> str:
    """Describe a YAML error by position only, never quoting the decrypted text.

    PyYAML error messages embed a snippet of the offending (already decrypted) line, which
    would leak secret material into dialogs and logs.

    Args:
        exc: Exception raised while parsing decrypted YAML.

    Returns:
        str: 'line N, column M' when known, otherwise the exception class name.
    """
    mark = getattr(exc, "problem_mark", None)
    if mark is not None:
        return f"line {mark.line + 1}, column {mark.column + 1}"
    return type(exc).__name__


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
        except PermissionError:
            raise
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
                filename=os.path.basename(vault_file), detail=_yaml_error_location(exc)
            )
        ) from exc

    return parsed


BACKUP_GENERATIONS = 5


def backup_path(vault_file: str, generation: int = 1) -> str:
    """Return the path of a backup generation (1 is the most recent: `<vault>.bak`).

    Args:
        vault_file: Path of the active vault file.
        generation: 1 for the latest backup, 2 for the one before it, and so on.

    Returns:
        str: `<vault>.bak` for generation 1, `<vault>.bak.N` for the others.
    """
    return f"{vault_file}.bak" if generation == 1 else f"{vault_file}.bak.{generation}"


def list_backup_generations(vault_file: str) -> List[int]:
    """Return the backup generations that exist on disk, newest first."""
    return [
        generation
        for generation in range(1, BACKUP_GENERATIONS + 1)
        if os.path.exists(backup_path(vault_file, generation))
    ]


def _rotate_backups(vault_file: str) -> None:
    """Shift older backups one generation back and copy the current file to generation 1."""
    for generation in range(BACKUP_GENERATIONS - 1, 0, -1):
        source = backup_path(vault_file, generation)
        if os.path.exists(source):
            os.replace(source, backup_path(vault_file, generation + 1))
    shutil.copy2(vault_file, backup_path(vault_file, 1))


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

    file_mode = 0o600
    if os.path.exists(vault_file):
        file_mode = stat.S_IMODE(os.stat(vault_file).st_mode)
        try:
            _rotate_backups(vault_file)
        except Exception as exc:
            raise RuntimeError(
                _(
                    "Could not create a backup of '{filename}'; save aborted to avoid data loss."
                ).format(filename=os.path.basename(vault_file))
            ) from exc

    yaml_str = yaml.dump(data, sort_keys=True, allow_unicode=True, default_flow_style=False)
    vault_lib = vault_lib_getter() if vault_lib_getter else get_vault_lib(password, vault_id)
    encrypted_bytes = vault_lib.encrypt(yaml_str.encode("utf-8"))

    temp_path = f"{vault_file}.tmp"
    # Create the temp file already restricted and keep the original permissions after replace
    fd = os.open(
        temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600
    )
    with os.fdopen(fd, "wb") as f:
        os.chmod(temp_path, file_mode)
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
    generation: int = 1,
) -> Optional[Tuple[str, bool]]:
    """Fetch variable payload from a backup (.bak, .bak.2, ...) vault file.

    Args:
        vault_file: Path to active vault file whose backup will be read.
        generation: Which backup to read (1 is the most recent).
        key: Variable key to retrieve.
        password: Plaintext password to decrypt the backup file.
        vault_id: Vault ID string.

    Returns:
        Optional[Tuple[str, bool]]: Payload string representation and is_binary flag if found, or None.

    Raises:
        RuntimeError: If reading or decrypting an existing backup file fails.
    """
    bak_file = backup_path(vault_file, generation)
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
