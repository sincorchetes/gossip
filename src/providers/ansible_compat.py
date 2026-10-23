"""POSIX compatibility shims and ctypes patches for Ansible on Windows/non-POSIX platforms."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from typing import Any, Optional, Tuple


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
                or (
                    sys.platform == "win32"
                    and any(k in name_str for k in ("msvcrt", "ucrt", "crt", "libc"))
                )
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

    from src.providers.ansible_shims import install_fake_posix_modules, patch_ansible_core

    install_fake_posix_modules()
    patch_ansible_core()
