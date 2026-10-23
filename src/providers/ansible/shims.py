"""Shims for Unix-specific modules and Ansible Core runtime patches on Windows."""

from __future__ import annotations

import os
import struct
import sys
import types
from typing import Any


def install_fake_posix_modules() -> None:
    """Inject mock modules for fcntl, termios, tty, pwd, and grp if missing."""
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
                mod.ioctl = lambda fd, op, arg=0, mutate_flag=True: struct.pack(
                    "HHHH", 24, 80, 0, 0
                )
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
                mod.getpwuid = lambda uid: (
                    "user",
                    "x",
                    1000,
                    1000,
                    "User",
                    "/home/user",
                    "/bin/bash",
                )
                mod.getpwnam = lambda name: (
                    "user",
                    "x",
                    1000,
                    1000,
                    "User",
                    "/home/user",
                    "/bin/bash",
                )
            else:
                mod.getgrgid = lambda gid: ("user", "x", 1000, ["user"])
                mod.getgrnam = lambda name: ("user", "x", 1000, ["user"])
            sys.modules[name] = mod


def patch_ansible_core() -> None:
    """Apply safety patches to Ansible Core's ConfigManager and Display classes."""
    try:
        import ansible.config.manager as acm

        if not getattr(acm.ConfigManager, "_gossip_yaml_patched", False):
            orig_read_yaml = acm.ConfigManager._read_config_yaml_file

            def _safe_read_config_yaml_file(self: Any, yml_file: Any) -> Any:
                yml_str = (
                    os.fsdecode(yml_file)
                    if isinstance(yml_file, (bytes, bytearray))
                    else str(yml_file)
                )
                if not os.path.exists(yml_str):
                    basename = os.path.basename(yml_str)
                    candidates = []
                    if getattr(sys, "frozen", False):
                        bundle_dir = getattr(
                            sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable))
                        )
                        candidates.extend(
                            [
                                os.path.join(bundle_dir, "ansible", "config", basename),
                                os.path.join(
                                    bundle_dir, "_internal", "ansible", "config", basename
                                ),
                                os.path.join(bundle_dir, "lib", "ansible", "config", basename),
                            ]
                        )
                    for cand in candidates:
                        if os.path.exists(cand):
                            return orig_read_yaml(self, cand)
                return orig_read_yaml(self, yml_file)

            acm.ConfigManager._read_config_yaml_file = _safe_read_config_yaml_file
            acm.ConfigManager._gossip_yaml_patched = True
    except Exception:  # pragma: no cover
        pass

    try:
        import ansible.utils.display as aud

        if not getattr(aud.Display, "_gossip_display_patched", False):
            orig_display = aud.Display.display

            def _safe_display(self: Any, *args: Any, **kwargs: Any) -> None:
                try:
                    return orig_display(self, *args, **kwargs)
                except (AttributeError, OSError):
                    pass

            aud.Display.display = _safe_display
            aud.Display._gossip_display_patched = True
    except Exception:  # pragma: no cover
        pass
