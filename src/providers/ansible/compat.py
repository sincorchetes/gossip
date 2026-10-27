"""POSIX compatibility shims and ctypes patches for Ansible on Windows/non-POSIX platforms."""

from __future__ import annotations

import contextlib
import ctypes
import ctypes.util
import os
import sys
from typing import Any, Callable, Iterator, Optional, Tuple


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


def ensure_windows_runtime() -> None:
    """Prepare the runtime that Ansible Core expects but a Windows GUI process lacks.

    This is permanent but only adds things that are missing:

    * valid ``sys.stdout``/``sys.stderr`` writers in windowed mode (PyInstaller sets them to
      None), and
    * stand-ins for the Unix-only modules ``fcntl``, ``termios``, ``tty``, ``pwd`` and ``grp``
      (a no-op on platforms that provide them).
    """
    if getattr(sys, "stdout", None) is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if getattr(sys, "stderr", None) is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    from src.providers.ansible.shims import install_fake_posix_modules

    install_fake_posix_modules()


def _swap(obj: Any, name: str, replacement: Any) -> Callable[[], None]:
    """Replace ``obj.name`` and return a function that puts the original back exactly.

    Args:
        obj: Module, class or instance holding the attribute.
        name: Attribute to replace.
        replacement: New value.

    Returns:
        Callable[[], None]: Restores the attribute (removing it again if it was inherited).
    """
    had_own = name in vars(obj)
    original = getattr(obj, name)
    setattr(obj, name, replacement)

    def restore() -> None:
        if had_own:
            setattr(obj, name, original)
        else:
            delattr(obj, name)

    return restore


def _libc_safe_load_library(original: Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Wrap ``ctypes.cdll.LoadLibrary`` so a missing or incomplete C runtime does not fail."""

    def _safe_load_library(name: Any) -> Any:
        """Handle a missing C library (find_library('c') returning None) or the Windows CRT.

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
            return original(name)
        except Exception:
            if sys.platform == "win32":
                return _MockLibc()
            raise

    return _safe_load_library


def _cdll_safe_getitem(original: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]:
    """Wrap ``ctypes.CDLL.__getitem__`` to supply wcwidth/wcswidth when the library lacks them."""

    def _safe_cdll_getitem(self: Any, name: Any) -> Any:
        """Catch missing wcwidth/wcswidth symbols during CDLL symbol resolution.

        Args:
            name: Symbol name requested on the library.

        Returns:
            Function pointer or MockLibcFunc fallback.
        """
        try:
            return original(self, name)
        except AttributeError:
            if isinstance(name, str) and name in ("wcwidth", "wcswidth"):
                func = _MockLibcFunc(1)
                setattr(self, name, func)
                return func
            raise

    return _safe_cdll_getitem


def _safe_get_context(original: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap ``multiprocessing.get_context`` so a 'fork' request falls back to the default."""

    def _get_context(method: Optional[str] = None) -> Any:
        """Fall back to the default multiprocessing context when 'fork' is unavailable.

        Args:
            method: Requested multiprocessing start method name.

        Returns:
            Multiprocessing context instance.
        """
        if method == "fork":
            return original()
        return original(method)

    return _get_context


def _utf8_getlocale(original: Callable[..., Tuple[Optional[str], Optional[str]]], default: int):
    """Wrap ``locale.getlocale`` so callers always see a UTF-8 encoding."""

    def _safe_getlocale(category: int = default) -> Tuple[Optional[str], Optional[str]]:
        """Return a UTF-8 encoding tuple when the platform reports another one or None.

        Args:
            category: Locale category to query.

        Returns:
            Tuple of (language_code, encoding).
        """
        lang, enc = original(category)
        if not enc or enc.lower() not in ("utf-8", "utf8"):
            return lang or "en_US", "UTF-8"
        return lang, enc

    return _safe_getlocale


@contextlib.contextmanager
def scoped_stdlib_patches() -> Iterator[None]:
    """Temporarily patch the standard-library calls Ansible Core makes while it is imported.

    Ansible's ``Display`` and multiprocessing helpers load libc, ask for the ``fork`` start
    method and read the locale at import time. On Windows those calls fail, so they are
    patched; the originals are restored on exit so nothing process-wide is left behind.
    """
    import locale
    import multiprocessing

    restores = [
        _swap(ctypes.cdll, "LoadLibrary", _libc_safe_load_library(ctypes.cdll.LoadLibrary)),
        _swap(ctypes.CDLL, "__getitem__", _cdll_safe_getitem(ctypes.CDLL.__getitem__)),
        _swap(locale, "getlocale", _utf8_getlocale(locale.getlocale, locale.LC_CTYPE)),
    ]
    if "fork" not in multiprocessing.get_all_start_methods():
        restores.append(
            _swap(multiprocessing, "get_context", _safe_get_context(multiprocessing.get_context))
        )
    try:
        yield
    finally:
        for restore in reversed(restores):
            restore()


@contextlib.contextmanager
def tty_ioctl_guard() -> Iterator[None]:
    """Tolerate ttys that reject TIOCGWINSZ while the wrapped block runs.

    Ansible's Display singleton calls ioctl(TIOCGWINSZ) on stdout during import whenever it is
    a tty. Some terminals (e.g. serial consoles or emulated macOS VMs) answer with ENOTTY,
    which would otherwise abort the whole GUI at startup. Inside the block a failed window-size
    query returns a zeroed size, so Ansible falls back to its default column width. The
    original fcntl.ioctl is restored on exit, so no process-wide patch is left behind.
    """
    if sys.platform == "win32":
        yield
        return

    import fcntl
    import termios

    orig_ioctl = fcntl.ioctl

    def _safe_ioctl(fd: Any, request: int, arg: Any = 0, mutate_flag: bool = True) -> Any:
        """Delegate to fcntl.ioctl, returning an empty window size when TIOCGWINSZ fails.

        Args:
            fd: File descriptor or object with fileno().
            request: ioctl request code.
            arg: Request argument (packed buffer for TIOCGWINSZ).
            mutate_flag: Whether a mutable buffer argument may be modified.

        Returns:
            Result of the underlying ioctl, or a zeroed buffer for a failed TIOCGWINSZ.
        """
        try:
            return orig_ioctl(fd, request, arg, mutate_flag)
        except OSError:
            if request == termios.TIOCGWINSZ and isinstance(arg, (bytes, bytearray)):
                return bytes(len(arg))
            raise

    fcntl.ioctl = _safe_ioctl
    try:
        yield
    finally:
        fcntl.ioctl = orig_ioctl


@contextlib.contextmanager
def ansible_import_context() -> Iterator[None]:
    """Everything needed to import Ansible Core on any platform, scoped to the import.

    Use it around the first import of ``ansible``::

        with ansible_import_context():
            from ansible.parsing.vault import VaultLib

    On exit it applies Gossip's small runtime fixes to Ansible itself (config lookup in frozen
    bundles, tolerant ``Display.display``) while the temporary patches are still active.
    """
    ensure_windows_runtime()
    with scoped_stdlib_patches(), tty_ioctl_guard():
        yield
        from src.providers.ansible.shims import patch_ansible_core

        patch_ansible_core()


if sys.platform == "win32":  # pragma: no cover
    ensure_windows_runtime()
