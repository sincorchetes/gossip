"""Show Gossip's own icon in the macOS Dock instead of the generic one of the launcher.

The bundle already names ``gossip.icns`` in its ``Info.plist``, but macOS keeps icons cached
by bundle identifier and path, so an app that was once installed with the default icon can keep
showing it. Setting the application icon while running does not depend on that cache.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from typing import Optional

from src.log import get_logger

log = get_logger(__name__)

ICON_NAME = "gossip.icns"


def find_icns() -> Optional[str]:
    """Path of the icon inside the .app bundle (``Contents/Resources``), or None.

    Looks next to the executable (``Contents/MacOS``) and in PyInstaller's data directory.
    """
    executable_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidates = [
        os.path.join(executable_dir, "..", "Resources", ICON_NAME),
        os.path.join(getattr(sys, "_MEIPASS", executable_dir), ICON_NAME),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return os.path.normpath(path)
    return None


def set_dock_icon() -> bool:  # pragma: no cover - needs the macOS Objective-C runtime
    """Set the Dock icon of the running process. Never raises; returns whether it was set."""
    if sys.platform != "darwin":
        return False
    path = find_icns()
    if path is None:
        return False
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "libobjc.dylib")
        ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit") or "AppKit")
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send = objc.objc_msgSend

        def call(target, selector, *args, argtypes=()):
            send.restype = ctypes.c_void_p
            send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
            return send(target, objc.sel_registerName(selector), *args)

        def cls(name: bytes):
            return objc.objc_getClass(name)

        ns_path = call(
            cls(b"NSString"), b"stringWithUTF8String:", path.encode(), argtypes=[ctypes.c_char_p]
        )
        image = call(
            call(cls(b"NSImage"), b"alloc"),
            b"initWithContentsOfFile:",
            ns_path,
            argtypes=[ctypes.c_void_p],
        )
        if not image:
            return False
        app = call(cls(b"NSApplication"), b"sharedApplication")
        call(app, b"setApplicationIconImage:", image, argtypes=[ctypes.c_void_p])
        return True
    except Exception:  # the icon is cosmetic: whatever goes wrong must not stop the app
        log.debug("Could not set the Dock icon", exc_info=True)
        return False
