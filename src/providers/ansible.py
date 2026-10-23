"""Ansible Vault encrypted YAML file provider implementation."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure UTF-8 locale environment defaults across platforms
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LANG", "C.UTF-8")
os.environ.setdefault("LC_ALL", "C.UTF-8")

import ctypes
import ctypes.util
import yaml


class _MockLibcFunc:
    """Mock implementation of standard C library functions (e.g. wcwidth, wcswidth)."""

    def __init__(self, default_ret: int = 1) -> None:
        """Initialize mock C function with default return code.

        Args:
            default_ret: Return value when no specific string length applies.
        """
        self.argtypes: Any = None
        self.restype: Any = ctypes.c_int
        self._default_ret = default_ret

    def __call__(self, *args: Any, **kwargs: Any) -> int:
        """Invoke mock C function and calculate width if string provided.

        Args:
            *args: Positional arguments passed to C function.
            **kwargs: Keyword arguments passed to C function.

        Returns:
            Calculated text length or default integer return code.
        """
        if args and isinstance(args[0], str):
            return len(args[0])
        return self._default_ret


class _MockLibc:
    """Mock implementation of the C standard library for Windows environments."""

    def __init__(self) -> None:
        """Initialize mock libc with wcwidth and wcswidth functions."""
        self.wcwidth = _MockLibcFunc(1)
        self.wcswidth = _MockLibcFunc(1)

    def __getitem__(self, name: str) -> Any:
        """Support dict-style or index lookup for libc functions (e.g. lib['wcwidth']).

        Args:
            name: Symbol name requested on libc.

        Returns:
            MockLibcFunc or fallback callable.
        """
        return getattr(self, name)

    def __getattr__(self, name: str) -> Any:
        """Fallback handler returning a callable for any unknown libc symbol.

        Args:
            name: Symbol name requested on libc.

        Returns:
            Callable returning 0.
        """
        return lambda *args, **kwargs: 0


def install_posix_shims() -> None:
    """Install mock POSIX compatibility modules on platforms lacking them (e.g. Windows).

    Ansible Core imports Unix-specific standard library modules ('fcntl', 'termios', 'tty',
    'pwd', 'grp'), requests the 'fork' multiprocessing context, and attempts to load libc
    solely for CLI/display operations. Installing lightweight shims allows Vault encryption
    and decryption routines to run cleanly on Windows.
    """
    import multiprocessing
    import struct
    import types

    # Ensure sys.stdout and sys.stderr are valid stream writers in GUI / windowed mode
    if getattr(sys, "stdout", None) is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if getattr(sys, "stderr", None) is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    # Patch ctypes.cdll.LoadLibrary to safely handle missing libc or Windows CRT lacking wcwidth
    if not getattr(ctypes.cdll, "_gossip_libc_patched", False):
        orig_load_library = ctypes.cdll.LoadLibrary

        def _safe_load_library(name: Any) -> Any:
            """Handle missing C library on Windows (e.g. find_library('c') returning None or msvcrt).

            Args:
                name: Name or path of the library to load.

            Returns:
                Loaded library or MockLibc fallback.
            """
            name_str = str(name).lower() if name is not None else ""
            if (
                name is None
                or name in ("c", "libc")
                or (sys.platform == "win32" and any(k in name_str for k in ("msvcrt", "ucrt", "crt", "libc")))
            ):
                return _MockLibc()
            try:
                return orig_load_library(name)
            except Exception:
                if sys.platform == "win32":
                    return _MockLibc()
                raise

        ctypes.cdll.LoadLibrary = _safe_load_library
        ctypes.cdll._gossip_libc_patched = True

    # Patch ctypes.CDLL.__getitem__ to safely supply wcwidth/wcswidth on platforms lacking them
    if not getattr(ctypes.CDLL, "_gossip_getitem_patched", False):
        orig_cdll_getitem = ctypes.CDLL.__getitem__

        def _safe_cdll_getitem(self: Any, name: Any) -> Any:
            """Catch missing wcwidth/wcswidth symbols on Windows CDLL symbol resolution.

            Args:
                name: Symbol name requested on library.

            Returns:
                Function pointer or MockLibcFunc fallback.
            """
            try:
                return orig_cdll_getitem(self, name)
            except AttributeError:
                if isinstance(name, str) and name in ("wcwidth", "wcswidth"):
                    func = _MockLibcFunc(1)
                    setattr(self, name, func)
                    return func
                raise

        ctypes.CDLL.__getitem__ = _safe_cdll_getitem
        ctypes.CDLL._gossip_getitem_patched = True

    # Patch multiprocessing to safely handle 'fork' context on Windows
    methods = multiprocessing.get_all_start_methods()
    if "fork" not in methods:
        orig_get_context = multiprocessing.get_context

        def _safe_get_context(method: Optional[str] = None) -> Any:
            """Fall back to default multiprocessing context when 'fork' is unavailable.

            Args:
                method: Requested multiprocessing start method name.

            Returns:
                Multiprocessing context instance.
            """
            if method == "fork":
                return orig_get_context()
            return orig_get_context(method)

        multiprocessing.get_context = _safe_get_context

    # Patch locale.getlocale to guarantee UTF-8 encoding on Windows
    import locale
    if not getattr(locale, "_gossip_locale_patched", False):
        orig_getlocale = locale.getlocale

        def _safe_getlocale(category: int = locale.LC_CTYPE) -> Tuple[Optional[str], Optional[str]]:
            """Return UTF-8 encoding tuple on Windows when queried by third-party CLI tools.

            Args:
                category: Locale category to query.

            Returns:
                Tuple of (language_code, encoding).
            """
            lang, enc = orig_getlocale(category)
            if not enc or enc.lower() not in ("utf-8", "utf8"):
                return lang or "en_US", "UTF-8"
            return lang, enc

        locale.getlocale = _safe_getlocale
        locale._gossip_locale_patched = True

    shims = ("fcntl", "termios", "tty", "pwd", "grp")
    for name in shims:
        if name not in sys.modules or sys.modules[name] is None:
            mod = types.ModuleType(name)
            if name == "fcntl":
                mod.F_GETFD = 1
                mod.F_SETFD = 2
                mod.FD_CLOEXEC = 1
                mod.fcntl = lambda *args, **kwargs: 0
                mod.flock = lambda *args, **kwargs: 0
                mod.lockf = lambda *args, **kwargs: 0
                mod.ioctl = lambda fd, op, arg=0, mutate_flag=True: struct.pack("HHHH", 24, 80, 0, 0)
            elif name == "termios":
                mod.TIOCGWINSZ = 0x5413
                mod.TCSAFLUSH = 2
                mod.TCSANOW = 0
                mod.TCSADRAIN = 1
                mod.TCIFLUSH = 0
                mod.BRKINT = mod.ICRNL = mod.INPCK = mod.ISTRIP = mod.IXON = 0
                mod.OPOST = mod.CSIZE = mod.PARENB = mod.CS8 = 0
                mod.ECHO = mod.ICANON = mod.IEXTEN = mod.ISIG = 0
                mod.VMIN = 6
                mod.VTIME = 5
                mod.VINTR = 0
                mod.VERASE = 2
                mod.tcgetattr = lambda fd: [0, 0, 0, 0, 0, 0, [0] * 32]
                mod.tcsetattr = lambda fd, when, mode: None
                mod.tcflush = lambda fd, queue: None
            elif name == "tty":
                mod.IFLAG = 0
                mod.OFLAG = 1
                mod.CFLAG = 2
                mod.LFLAG = 3
                mod.ISPEED = 4
                mod.OSPEED = 5
                mod.CC = 6
                mod.setraw = lambda fd, when=0: None
                mod.setcbreak = lambda fd, when=0: None
            elif name == "pwd":
                mod.getpwuid = lambda uid: ("user", "x", 1000, 1000, "User", "/home/user", "/bin/bash")
                mod.getpwnam = lambda name: ("user", "x", 1000, 1000, "User", "/home/user", "/bin/bash")
            else:
                mod.getgrgid = lambda gid: ("user", "x", 1000, ["user"])
                mod.getgrnam = lambda name: ("user", "x", 1000, ["user"])
            sys.modules[name] = mod

    # Patch ansible.config.manager.ConfigManager._read_config_yaml_file to locate base.yml
    # in frozen PyInstaller bundles across bundle layout variants
    try:
        import ansible.config.manager as acm
        if not getattr(acm.ConfigManager, "_gossip_yaml_patched", False):
            orig_read_yaml = acm.ConfigManager._read_config_yaml_file

            def _safe_read_config_yaml_file(self: Any, yml_file: Any) -> Any:
                """Read YAML configuration, falling back to bundle search paths if missing.

                Args:
                    yml_file: Path to YAML configuration file.

                Returns:
                    Parsed YAML dictionary configuration.
                """
                yml_str = os.fsdecode(yml_file) if isinstance(yml_file, (bytes, bytearray)) else str(yml_file)
                if not os.path.exists(yml_str):
                    basename = os.path.basename(yml_str)
                    candidates = []
                    if getattr(sys, "frozen", False):
                        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
                        candidates.extend([
                            os.path.join(bundle_dir, "ansible", "config", basename),
                            os.path.join(bundle_dir, "_internal", "ansible", "config", basename),
                            os.path.join(bundle_dir, "lib", "ansible", "config", basename),
                        ])
                    for cand in candidates:
                        if os.path.exists(cand):
                            return orig_read_yaml(self, cand)
                return orig_read_yaml(self, yml_file)

            acm.ConfigManager._read_config_yaml_file = _safe_read_config_yaml_file
            acm.ConfigManager._gossip_yaml_patched = True
    except Exception:  # pragma: no cover
        pass

    # Patch ansible.utils.display.Display.display to suppress write errors when streams lack write()
    try:
        import ansible.utils.display as aud
        if not getattr(aud.Display, "_gossip_display_patched", False):
            orig_display = aud.Display.display

            def _safe_display(self: Any, *args: Any, **kwargs: Any) -> None:
                """Safely write to stream, ignoring missing write attributes in GUI mode.

                Args:
                    *args: Positional arguments for display.
                    **kwargs: Keyword arguments for display.
                """
                try:
                    return orig_display(self, *args, **kwargs)
                except (AttributeError, OSError):
                    pass

            aud.Display.display = _safe_display
            aud.Display._gossip_display_patched = True
    except Exception:  # pragma: no cover
        pass


install_posix_shims()

from ansible.parsing.vault import AnsibleVaultError, VaultLib, VaultSecret

from src.providers.base import BaseSecretProvider
from src.exceptions import AuthenticationError, PermissionDeniedError, ProviderError, ResourceNotFoundError
from src.i18n import _
from src.models import SecretItem, SecretVersionItem


class AnsibleVaultClient(BaseSecretProvider):
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

        # In-memory cache of decrypted dictionary
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
            """Update Ansible Vault file and credentials, invoking completion callback."""
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
        """Return the Ansible Vault identifier string (default: 'default')."""
        return self._vault_id

    @vault_id.setter
    def vault_id(self, val: str) -> None:
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

    @classmethod
    def detect_password_file(cls) -> Optional[str]:
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

    @classmethod
    def detect_password(cls) -> Optional[str]:
        """Detect plaintext vault password from environment or password file.

        Returns:
            Optional[str]: Detected password string or None.
        """
        env_pass = os.getenv("ANSIBLE_VAULT_PASSWORD")
        if env_pass:
            return env_pass

        pass_file = cls.detect_password_file()
        if pass_file and os.path.exists(pass_file):
            try:
                with open(pass_file, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return None

    @classmethod
    def find_local_vault_files(cls) -> List[str]:
        """Scan current workspace directory for Ansible Vault encrypted files.

        Returns:
            List[str]: List of discovered encrypted file paths.
        """
        results: List[str] = []
        cwd = os.getcwd()
        try:
            for root, dirs, files in os.walk(cwd):
                # Ignore hidden dirs or common virtualenvs
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")]
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
        pwd = self._get_active_password()
        if not pwd:
            raise PermissionError(
                "No se ha proporcionado ninguna contraseña para desbloquear el Ansible Vault.\n"
                "Introduce la contraseña o selecciona tu archivo .vault_pass."
            )
        secret = VaultSecret(pwd.encode("utf-8"))
        vault_id = self.vault_id or "default"
        return VaultLib([(vault_id, secret)])

    def unlock(
        self,
        vault_file: Optional[str] = None,
        password: Optional[str] = None,
        password_file: Optional[str] = None,
        vault_id: Optional[str] = None,
    ) -> bool:
        """Attempt to decrypt the target vault file using provided credentials.

        Args:
            vault_file: Optional path to vault file to set before unlock.
            password: Optional plaintext password.
            password_file: Optional path to password file.
            vault_id: Optional vault ID string.

        Returns:
            bool: True if decryption succeeded, False otherwise.
        """
        if vault_file:
            self.vault_file = vault_file
        if password is not None:
            self._password = password
        if password_file is not None:
            self._password_file = password_file
        if vault_id is not None:
            self._vault_id = vault_id

        # Force reload
        self._invalidate_cache()
        self._load_data()
        return True

    def _load_data(self) -> Dict[str, Any]:
        """Loads and decrypts the active vault file, returning a dictionary."""
        vf = self.vault_file
        if not vf:
            raise FileNotFoundError(
                "No se ha seleccionado ningún archivo de Ansible Vault.\n"
                "Usa el botón de selección para elegir o crear un archivo vault.yml."
            )

        if not os.path.exists(vf):
            raise FileNotFoundError(f"El archivo de Ansible Vault '{vf}' no existe.")

        current_mtime = os.path.getmtime(vf)
        if self._cached_dict is not None and self._cached_mtime == current_mtime:
            return self._cached_dict

        with open(vf, "rb") as f:
            raw_bytes = f.read()

        if not raw_bytes.strip():
            self._cached_dict = {}
            self._cached_mtime = current_mtime
            self._is_unlocked = True
            return self._cached_dict

        if raw_bytes.startswith(b"$ANSIBLE_VAULT"):
            try:
                vault_lib = self._get_vault_lib()
                plaintext_bytes = vault_lib.decrypt(raw_bytes)
                plaintext = plaintext_bytes.decode("utf-8")
            except AnsibleVaultError as exc:
                self._is_unlocked = False
                raise PermissionError(
                    f"Contraseña incorrecta o fallo al descifrar Ansible Vault '{os.path.basename(vf)}'.\n"
                    f"Detalle: {exc}"
                ) from exc
            except Exception as exc:
                self._is_unlocked = False
                raise RuntimeError(f"Error al descifrar Ansible Vault: {exc}") from exc
        else:
            # File is not encrypted yet
            plaintext = raw_bytes.decode("utf-8", errors="replace")

        try:
            parsed = yaml.safe_load(plaintext)
            if parsed is None:
                parsed = {}
            elif not isinstance(parsed, dict):
                # Wrap scalar or list
                parsed = {"content": parsed}
        except Exception as exc:
            raise RuntimeError(f"El contenido descifrado de '{os.path.basename(vf)}' no es un YAML válido: {exc}") from exc

        self._cached_dict = parsed
        self._cached_mtime = current_mtime
        self._is_unlocked = True
        return self._cached_dict

    def _save_data(self, data: Dict[str, Any]) -> None:
        """Serializes dictionary to YAML, encrypts with VaultLib, and saves atomically."""
        vf = self.vault_file
        if not vf:
            raise ValueError("No se ha configurado la ruta del archivo Ansible Vault.")

        # Create parent directory if needed
        os.makedirs(os.path.dirname(os.path.abspath(vf)), exist_ok=True)

        # Create backup copy if original file exists
        if os.path.exists(vf):
            bak_path = f"{vf}.bak"
            try:
                shutil.copy2(vf, bak_path)
            except Exception:
                pass

        # Dump dictionary to YAML
        yaml_str = yaml.dump(data, sort_keys=True, allow_unicode=True, default_flow_style=False)

        # Encrypt
        vault_lib = self._get_vault_lib()
        encrypted_bytes = vault_lib.encrypt(yaml_str.encode("utf-8"))

        # Write atomically via temp file
        temp_path = f"{vf}.tmp"
        with open(temp_path, "wb") as f:
            f.write(encrypted_bytes)
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, vf)

        self._cached_dict = data
        self._cached_mtime = os.path.getmtime(vf)
        self._is_unlocked = True

    def list_secrets(self) -> List[SecretItem]:
        """List all variables stored in the active Ansible Vault file.

        Returns:
            List[SecretItem]: List of normalized secret item instances.

        Raises:
            AuthenticationError: If decryption password is missing or invalid.
            FileNotFoundError: If the target vault file does not exist.
        """
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
        """List version and backup information for an Ansible Vault variable.

        Args:
            secret_name: Identifier formatted as '{vault_file}::{key}'.

        Returns:
            List[SecretVersionItem]: Current and optional previous (.bak) versions.
        """
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

        # Check if .bak file exists and has previous version
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

    def access_secret_payload(self, secret_name: str, version: Optional[str] = None) -> Tuple[str, bool]:
        """Fetch the decrypted value of an Ansible Vault variable.

        Args:
            secret_name: Variable name or resource path.
            version: Optional version identifier ('1' or '0'/'backup').

        Returns:
            Tuple[str, bool]: Decoded payload string and is_binary boolean flag.

        Raises:
            KeyError: If the variable does not exist in the decrypted dictionary.
        """
        key = secret_name.split("::")[-1]

        # If requesting backup version
        if version in ("0", "backup", "AWSPREVIOUS"):
            bak_file = f"{self.vault_file}.bak"
            if os.path.exists(bak_file):
                try:
                    with open(bak_file, "rb") as f:
                        bak_bytes = f.read()
                    vault_lib = self._get_vault_lib()
                    bak_plain = vault_lib.decrypt(bak_bytes).decode("utf-8")
                    bak_data = yaml.safe_load(bak_plain) or {}
                    if key in bak_data:
                        val = bak_data[key]
                        if isinstance(val, (dict, list)):
                            return yaml.dump(val, sort_keys=False, default_flow_style=False), False
                        return str(val), False
                except Exception as exc:
                    raise RuntimeError(f"No se pudo leer la versión de copia de seguridad: {exc}") from exc

        data = self._load_data()
        if key not in data:
            raise KeyError(f"La variable '{key}' no existe en el archivo Ansible Vault.")

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
        """Add a new secret variable to the Ansible Vault file.

        Args:
            secret_id: Key name for the variable.
            payload_data: String value to store (parsed as YAML/JSON if valid).
            labels: Optional dictionary of labels.
            description: Optional note or description.

        Returns:
            SecretItem: Newly created secret metadata.

        Raises:
            ValueError: If the variable key already exists in the file.
        """
        data = self._load_data()
        if secret_id in data:
            raise ValueError(f"La variable '{secret_id}' ya existe en el vault. Usa 'Añadir versión' para modificarla.")

        # Attempt to parse as YAML/JSON scalar or structure if applicable
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
        """Update the payload of an existing Ansible Vault variable.

        Args:
            secret_name_or_id: Variable key or resource path.
            payload_data: New string value to store.

        Returns:
            SecretVersionItem: Newly created version metadata.
        """
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
        """Remove a variable from the Ansible Vault file.

        Args:
            secret_name_or_id: Variable key or resource path to remove.
        """
        key = secret_name_or_id.split("::")[-1]
        data = self._load_data()
        if key in data:
            del data[key]
            self._save_data(data)

    def _parse_payload(self, text: str) -> Any:
        """Smart parser for user payload: tries YAML/JSON or keeps string."""
        stripped = text.strip()
        # If looks like YAML dict, list, boolean, number, or quoted string, try safe_load
        if stripped.startswith(("{", "[")) or stripped in ("true", "false", "yes", "no"):
            try:
                return yaml.safe_load(stripped)
            except Exception:
                pass
        return text

    def create_new_vault_file(self, file_path: str, password: str, initial_data: Optional[Dict] = None) -> None:
        """Create a new encrypted Ansible Vault file with initial data.

        Args:
            file_path: Target filesystem path for the vault file.
            password: Plaintext password used to encrypt the new file.
            initial_data: Optional dictionary of initial variables to write.
        """
        self.vault_file = file_path
        self._password = password
        self._save_data(initial_data or {})
