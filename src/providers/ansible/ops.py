"""CRUD operations mixin for Ansible Vault provider."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import yaml

from src.i18n import _
from src.log import get_logger
from src.models import SecretItem, SecretVersionItem
from src.providers.ansible.discovery import read_password_file
from src.providers.ansible.vault import (
    backup_path,
    get_vault_lib,
    list_backup_generations,
    load_vault_data,
    parse_vault_payload,
    read_backup_payload,
    save_vault_data,
)
from src.providers.errors import CONFLICT, MISSING, provider_error

if TYPE_CHECKING:
    from ansible.parsing.vault import VaultLib

log = get_logger(__name__)


_BACKUP_SUFFIX = re.compile(r"backup(\d*)")


def _split_version_suffix(key: str, version: Optional[str]) -> Tuple[str, Optional[str]]:
    """Split the variable and version parts of names produced by list_versions.

    Args:
        key: Variable name, optionally followed by a version suffix (1, 0, backup or backupN).
        version: Explicit version requested by the caller, if any.

    Returns:
        Tuple[str, Optional[str]]: The variable name and the version to read.
    """
    base, sep, suffix = key.rpartition("@")
    if sep and base and (suffix in ("0", "1") or _BACKUP_SUFFIX.fullmatch(suffix)):
        return base, version or suffix
    return key, version


def _backup_generation(version: Optional[str]) -> Optional[int]:
    """Map a version identifier to a backup generation (1 is the most recent), if it is one.

    Args:
        version: Version identifier such as "0", "backup", "AWSPREVIOUS" or "backup3".

    Returns:
        Optional[int]: The generation number, or None for the current version.
    """
    if version in ("0", "AWSPREVIOUS"):
        return 1
    match = _BACKUP_SUFFIX.fullmatch(version or "")
    return int(match.group(1) or 1) if match else None


class AnsibleOperationsMixin:
    """Provides secret listing, versioning, CRUD, and payload access for Ansible Vault."""

    vault_file: Optional[str]
    vault_id: str
    _password: Optional[str]
    _password_file: Optional[str]
    _cached_dict: Optional[Dict[str, Any]]
    _cached_mtime: Optional[float]
    _is_unlocked: bool

    def _invalidate_cache(self) -> None: ...

    def _get_active_password(self) -> Optional[str]:
        """Return the active in-memory password or read from password file."""
        if self._password:
            return self._password
        if self._password_file:
            return read_password_file(self._password_file)
        return None

    def _get_vault_lib(self) -> VaultLib:
        """Construct and configure an Ansible VaultLib instance with active secret."""
        pwd = self._get_active_password()
        if not pwd:
            raise PermissionError(
                _(
                    "No password provided to unlock Ansible Vault.\n"
                    "Enter password or select your .vault_pass file."
                )
            )
        return get_vault_lib(pwd, self.vault_id)

    def unlock(
        self,
        vault_file: Optional[str] = None,
        password: Optional[str] = None,
        password_file: Optional[str] = None,
        vault_id: Optional[str] = None,
    ) -> bool:
        """Attempt to decrypt the target vault file using provided credentials."""
        if vault_file:
            self.vault_file = vault_file
        if password is not None:
            self._password = password
        if password_file is not None:
            self._password_file = password_file
        if vault_id is not None:
            self._vault_id = vault_id

        self._invalidate_cache()
        self._load_data()
        return True

    def _load_data(self) -> Dict[str, Any]:
        """Loads and decrypts the active vault file, returning a dictionary."""
        vf = self.vault_file
        if not vf:
            raise FileNotFoundError(
                _(
                    "No Ansible Vault file selected.\n"
                    "Use the file switcher button to choose or create a vault.yml file."
                )
            )

        if not os.path.exists(vf):
            raise FileNotFoundError(
                _("The Ansible Vault file '{path}' does not exist.").format(path=vf)
            )

        current_mtime = os.path.getmtime(vf)
        if self._cached_dict is not None and self._cached_mtime == current_mtime:
            return self._cached_dict

        try:
            pwd = self._get_active_password()
            data = load_vault_data(vf, pwd, self.vault_id, vault_lib_getter=self._get_vault_lib)
        except Exception:
            self._is_unlocked = False
            raise

        self._cached_dict = data
        self._cached_mtime = current_mtime
        self._is_unlocked = True
        return self._cached_dict

    def _save_data(self, data: Dict[str, Any]) -> None:
        """Serializes dictionary to YAML, encrypts with VaultLib, and saves atomically."""
        vf = self.vault_file
        if not vf:
            raise ValueError(_("Ansible Vault file path is not configured."))

        pwd = self._get_active_password()
        try:
            save_vault_data(
                vf, data, pwd or "", self.vault_id, vault_lib_getter=self._get_vault_lib
            )
        except Exception:
            # Callers mutate the cached dict before saving; drop it so the next read hits disk
            self._invalidate_cache()
            raise
        self._cached_dict = data
        self._cached_mtime = os.path.getmtime(vf)
        self._is_unlocked = True

    def list_secrets(self) -> List[SecretItem]:
        """List all variables stored in the active Ansible Vault file."""
        data = self._load_data()
        vf = self.vault_file or ""
        file_mtime = datetime.fromtimestamp(os.path.getmtime(vf)) if os.path.exists(vf) else None

        secrets: List[SecretItem] = []
        for key, val in data.items():
            type_name = type(val).__name__
            val_str = str(val)
            desc = _("{type} ({count} characters)").format(type=type_name, count=len(val_str))
            secrets.append(
                SecretItem(
                    name=f"{vf}::{key}",
                    secret_id=str(key),
                    provider="ansible",
                    description=desc,
                    create_time=file_mtime,
                    last_changed_date=file_mtime,
                    labels={"type": type_name},
                    replication_type="AUTOMATIC",
                    locations=[os.path.basename(vf)],
                )
            )

        secrets.sort(key=lambda s: s.secret_id.lower())
        return secrets

    def _backup_value(
        self, vault_file: str, key: str, generation: int
    ) -> Optional[Tuple[str, bool]]:
        """Read a variable from a backup generation, or None if it was not there."""
        return read_backup_payload(
            vault_file,
            key,
            self._get_active_password() or "",
            self.vault_id,
            vault_lib_getter=self._get_vault_lib,
            generation=generation,
        )

    def list_versions(self, secret_name: str) -> List[SecretVersionItem]:
        """List version and backup information for an Ansible Vault variable."""
        key = secret_name.split("::")[-1]
        vf = self.vault_file or ""
        file_mtime = datetime.fromtimestamp(os.path.getmtime(vf)) if os.path.exists(vf) else None

        versions: List[SecretVersionItem] = [
            SecretVersionItem(
                version_id="1",
                name=f"{key}@1",
                state="ENABLED",
                stages=["AWSCURRENT"],
                create_time=file_mtime,
                destroy_time=None,
            )
        ]

        for generation in list_backup_generations(vf):
            try:
                # Only offer backups in which the variable already existed
                if self._backup_value(vf, key, generation) is None:
                    continue
                bak_mtime = datetime.fromtimestamp(os.path.getmtime(backup_path(vf, generation)))
            except Exception:
                log.debug("could not read backup %d", generation, exc_info=True)
                continue
            latest = generation == 1
            versions.append(
                SecretVersionItem(
                    version_id="0" if latest else str(1 - generation),
                    name=f"{key}@backup" if latest else f"{key}@backup{generation}",
                    state="DISABLED",
                    stages=["AWSPREVIOUS"] if latest else [_("Backup %d") % generation],
                    create_time=bak_mtime,
                    destroy_time=None,
                )
            )

        return versions

    def access_secret_payload(
        self, secret_name: str, version: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Fetch the decrypted value of an Ansible Vault variable."""
        raw_key = secret_name.split("::")[-1]
        key, version = _split_version_suffix(raw_key, version)

        generation = _backup_generation(version)
        if generation is not None:
            vf = self.vault_file or ""
            bak_res = self._backup_value(vf, key, generation)
            if bak_res is None:
                raise provider_error(
                    MISSING,
                    _("The variable '{variable}' does not exist in that backup.").format(
                        variable=key
                    ),
                    "ansible",
                )
            return bak_res

        data = self._load_data()
        if key not in data and raw_key in data:
            key = raw_key  # the variable name itself contains an "@"
        if key not in data:
            raise provider_error(
                MISSING,
                _("The variable '{variable}' does not exist in the Ansible Vault file.").format(
                    variable=key
                ),
                "ansible",
            )

        val = data[key]
        if isinstance(val, (dict, list)):
            return yaml.dump(val, sort_keys=False, default_flow_style=False), False
        return str(val), False

    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        """Add a new secret variable to the Ansible Vault file."""
        return self._store_new_secret(
            secret_id, self._parse_payload(payload_data), len(payload_data)
        )

    def create_native_secret(
        self,
        secret_id: str,
        value: Any,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        """Add a variable keeping the exact Python type of ``value`` (int, bool, dict, ...)."""
        return self._store_new_secret(secret_id, value, len(str(value)))

    def _store_new_secret(self, secret_id: str, value: Any, length: int) -> SecretItem:
        """Write a new variable to the vault and describe it as a SecretItem."""
        data = self._load_data()
        if secret_id in data:
            raise provider_error(
                CONFLICT,
                _(
                    "The variable '{variable}' already exists in the vault. Use 'New Version' to modify it."
                ).format(variable=secret_id),
                "ansible",
            )

        data[secret_id] = value
        self._save_data(data)

        vf = self.vault_file or ""
        file_mtime = datetime.fromtimestamp(os.path.getmtime(vf))
        type_name = type(value).__name__

        return SecretItem(
            name=f"{vf}::{secret_id}",
            secret_id=secret_id,
            provider="ansible",
            description=_("{type} ({count} characters)").format(type=type_name, count=length),
            create_time=file_mtime,
            last_changed_date=file_mtime,
            labels={"type": type_name},
            replication_type="AUTOMATIC",
            locations=[os.path.basename(vf)],
        )

    def add_secret_version(self, secret_name_or_id: str, payload_data: str) -> SecretVersionItem:
        """Update the payload of an existing Ansible Vault variable."""
        key = secret_name_or_id.split("::")[-1]
        data = self._load_data()

        parsed_val = self._parse_payload(payload_data)
        data[key] = parsed_val
        self._save_data(data)

        vf = self.vault_file or ""
        file_mtime = datetime.fromtimestamp(os.path.getmtime(vf))
        return SecretVersionItem(
            version_id="1",
            name=f"{key}@1",
            state="ENABLED",
            stages=["AWSCURRENT"],
            create_time=file_mtime,
            destroy_time=None,
        )

    def delete_secret(self, secret_name_or_id: str) -> None:
        """Remove a variable from the Ansible Vault file."""
        key = secret_name_or_id.split("::")[-1]
        data = self._load_data()
        if key in data:
            del data[key]
            self._save_data(data)

    def _parse_payload(self, text: str) -> Any:
        return parse_vault_payload(text)

    def create_new_vault_file(
        self, file_path: str, password: str, initial_data: Optional[Dict] = None
    ) -> None:
        """Create a new encrypted Ansible Vault file with initial data."""
        self.vault_file = file_path
        self._password = password
        self._save_data(initial_data or {})
