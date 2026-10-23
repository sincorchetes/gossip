"""Ansible Vault encrypted YAML file client class."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

# Ensure UTF-8 locale environment defaults across platforms
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LANG", "C.UTF-8")
os.environ.setdefault("LC_ALL", "C.UTF-8")

from ansible.parsing.vault import AnsibleVaultError, VaultLib, VaultSecret  # noqa: F401

from src.i18n import _
from src.providers.ansible.compat import (
    install_posix_shims,
)
from src.providers.ansible.discovery import (
    detect_password,
    detect_password_file,
    detect_vault_file,
    find_local_vault_files,
)
from src.providers.ansible.ops import AnsibleOperationsMixin
from src.providers.base import BaseSecretProvider

install_posix_shims()


class AnsibleVaultClient(AnsibleOperationsMixin, BaseSecretProvider):
    """Provider implementation for Ansible Vault encrypted YAML files."""

    def __init__(
        self,
        vault_file: Optional[str] = None,
        password: Optional[str] = None,
        password_file: Optional[str] = None,
        vault_id: str = "default",
    ):
        """Initialize the Ansible Vault client.

        Args:
            vault_file: Path to encrypted Ansible Vault YAML file.
            password: Optional decryption password.
            password_file: Optional path to vault password file (.vault_pass).
            vault_id: Ansible vault ID identifier (defaults to 'default').
        """
        self._vault_file: Optional[str] = vault_file or self.detect_vault_file()
        self._password: Optional[str] = password or self.detect_password()
        self._password_file: Optional[str] = password_file or self.detect_password_file()
        self._vault_id: str = vault_id or "default"

        self._cached_dict: Optional[Dict[str, Any]] = None
        self._cached_mtime: Optional[float] = None
        self._is_unlocked: bool = False

    @property
    def provider_id(self) -> str:
        """Return the unique provider identifier string ('ansible')."""
        return "ansible"

    @property
    def provider(self) -> str:
        """Return the provider identifier string (alias for provider_id)."""
        return "ansible"

    @property
    def display_name(self) -> str:
        """Return the human-readable provider name shown in the UI switcher."""
        return "Ansible Vault"

    @property
    def icon_name(self) -> str:
        """Return the FreeDesktop symbolic icon name for the context switcher button."""
        return "document-open-symbolic"

    @property
    def context_title(self) -> str:
        """Return the localized context title for dialog headers."""
        return _("Ansible Vault")

    @property
    def context_subtitle(self) -> str:
        """Return the localized subtitle with active Ansible Vault filename."""
        vf = self.vault_file
        fname = os.path.basename(vf) if vf else _("No vault selected")
        return _("Ansible Vault: %s") % fname

    @property
    def context_btn_tooltip(self) -> str:
        """Return the localized tooltip for the vault switcher button."""
        return _("Switch Ansible Vault File & Password")

    @property
    def loading_message(self) -> str:
        """Return the localized message shown while decrypting Ansible Vault."""
        return _("Decrypting Ansible Vault...")

    @property
    def empty_message(self) -> str:
        """Return the localized message shown when no variables exist in this Ansible Vault."""
        return _("No variables found in this Ansible Vault.")

    @property
    def error_message(self) -> str:
        """Return the localized message shown when unlock or read fails."""
        return _("Could not unlock or read Ansible Vault.")

    @property
    def supports_version_toggling(self) -> bool:
        """Return False indicating Ansible Vault does not support version toggles."""
        return False

    @property
    def supports_version_destroy(self) -> bool:
        """Return False indicating Ansible Vault does not support version destruction."""
        return False

    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        """Open the modal dialog to select, unlock, or configure an Ansible Vault file.

        Args:
            parent_window: GTK parent window to transient the dialog for.
            on_success: Callback function invoked after successful unlock.
        """
        from src.ui.dialogs import show_change_ansible_vault_dialog

        def on_confirm(vault_file: str, password: Optional[str], pass_file: Optional[str]) -> None:
            self.vault_file = vault_file
            if password is not None:
                self.password = password
            if pass_file is not None:
                self.password_file = pass_file
            on_success()

        show_change_ansible_vault_dialog(parent_window, self, on_confirm)

    @property
    def vault_file(self) -> Optional[str]:
        """Return the absolute filesystem path to the active Ansible Vault file."""
        if not self._vault_file:
            self._vault_file = self.detect_vault_file()
        return self._vault_file

    @vault_file.setter
    def vault_file(self, val: Optional[str]) -> None:
        """Set target Ansible Vault file path and invalidate in-memory decryption cache."""
        new_val = os.path.abspath(val.strip()) if val and val.strip() else None
        if new_val != self._vault_file:
            self._vault_file = new_val
            self._invalidate_cache()

    @property
    def password(self) -> Optional[str]:
        """Return the plaintext decryption password, autodetecting if not explicitly set."""
        if not self._password:
            self._password = self.detect_password()
        return self._password

    @password.setter
    def password(self, val: Optional[str]) -> None:
        """Set plaintext decryption password and invalidate cache."""
        self._password = val.strip() if val else None
        self._invalidate_cache()

    @property
    def password_file(self) -> Optional[str]:
        """Return the filesystem path to the active vault password file (.vault_pass)."""
        if not self._password_file:
            self._password_file = self.detect_password_file()
        return self._password_file

    @password_file.setter
    def password_file(self, val: Optional[str]) -> None:
        """Set vault password file path and invalidate cache."""
        self._password_file = os.path.abspath(val.strip()) if val and val.strip() else None
        self._invalidate_cache()

    @property
    def vault_id(self) -> str:
        """Return the active Ansible Vault identifier."""
        return self._vault_id

    @vault_id.setter
    def vault_id(self, val: Optional[str]) -> None:
        """Set the Ansible Vault identifier string."""
        self._vault_id = val.strip() if val else "default"
        self._invalidate_cache()

    @property
    def is_unlocked(self) -> bool:
        """Return True if the vault is unlocked with valid in-memory decrypted data."""
        return self._is_unlocked and self._cached_dict is not None

    def _invalidate_cache(self) -> None:
        """Clear in-memory decrypted YAML cache and reset unlocked flag."""
        self._cached_dict = None
        self._cached_mtime = None
        self._is_unlocked = False

    @classmethod
    def detect_vault_file(cls) -> Optional[str]:
        return detect_vault_file()

    @classmethod
    def detect_password_file(cls) -> Optional[str]:
        return detect_password_file()

    @classmethod
    def detect_password(cls) -> Optional[str]:
        return detect_password(cls.detect_password_file)

    @classmethod
    def find_local_vault_files(cls) -> List[str]:
        return find_local_vault_files()
