"""CRUD operations mixin for Ansible Vault provider."""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import yaml

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers.ansible_vault import (
    parse_vault_payload,
    read_backup_payload,
)

if TYPE_CHECKING:
    from ansible.parsing.vault import VaultLib


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
        if self._password_file and os.path.exists(self._password_file):
            try:
                with open(self._password_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return None

    def _get_vault_lib(self) -> VaultLib:
        """Construct and configure an Ansible VaultLib instance with active secret."""
        from src.providers.ansible_vault import get_vault_lib

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
        from src.providers.ansible_vault import load_vault_data

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
        from src.providers.ansible_vault import save_vault_data

        vf = self.vault_file
        if not vf:
            raise ValueError(_("Ansible Vault file path is not configured."))

        pwd = self._get_active_password()
        save_vault_data(vf, data, pwd or "", self.vault_id, vault_lib_getter=self._get_vault_lib)
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
            desc = f"{type_name} ({len(val_str)} caracteres)"
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

        bak_file = f"{vf}.bak"
        if os.path.exists(bak_file):
            try:
                bak_mtime = datetime.fromtimestamp(os.path.getmtime(bak_file))
                versions.append(
                    SecretVersionItem(
                        version_id="0",
                        name=f"{key}@backup",
                        state="DISABLED",
                        stages=["AWSPREVIOUS"],
                        create_time=bak_mtime,
                        destroy_time=None,
                    )
                )
            except Exception:
                pass

        return versions

    def access_secret_payload(
        self, secret_name: str, version: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Fetch the decrypted value of an Ansible Vault variable."""
        key = secret_name.split("::")[-1]

        if version in ("0", "backup", "AWSPREVIOUS"):
            vf = self.vault_file or ""
            pwd = self._get_active_password() or ""
            bak_res = read_backup_payload(
                vf, key, pwd, self.vault_id, vault_lib_getter=self._get_vault_lib
            )
            if bak_res is not None:
                return bak_res

        data = self._load_data()
        if key not in data:
            raise KeyError(
                _("The variable '{variable}' does not exist in the Ansible Vault file.").format(
                    variable=key
                )
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
        data = self._load_data()
        if secret_id in data:
            raise ValueError(
                _(
                    "The variable '{variable}' already exists in the vault. Use 'New Version' to modify it."
                ).format(variable=secret_id)
            )

        parsed_val = self._parse_payload(payload_data)
        data[secret_id] = parsed_val
        self._save_data(data)

        vf = self.vault_file or ""
        file_mtime = datetime.fromtimestamp(os.path.getmtime(vf))
        type_name = type(parsed_val).__name__

        return SecretItem(
            name=f"{vf}::{secret_id}",
            secret_id=secret_id,
            provider="ansible",
            description=f"{type_name} ({len(payload_data)} caracteres)",
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
