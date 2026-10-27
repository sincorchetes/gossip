"""Main entry point for the Gossip multi-cloud secret manager CLI and GUI."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

# Ensure UTF-8 mode and safe environment defaults across operating systems
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LANG", "C.UTF-8")
os.environ.setdefault("LC_ALL", "C.UTF-8")
# Prevent google-auth from hanging on GCE metadata server (169.254.169.254) in desktop environments
os.environ.setdefault("NO_GCE_CHECK", "true")

# In Windows GUI / PyInstaller --windowed environments, standard streams are None.
# Provide null writers to prevent AttributeError: 'NoneType' object has no attribute 'write'.
if sys.stdout is None:  # pragma: no cover
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:  # pragma: no cover
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure src is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import __version__, registry, state
from src.bootstrap import setup_frozen_environment
from src.i18n import _, init_i18n

setup_frozen_environment()

if sys.platform == "win32":  # pragma: no cover
    from src.providers.ansible.compat import ensure_windows_runtime

    ensure_windows_runtime()


def _preparse_language(argv: List[str]) -> Optional[str]:
    """Read --lang/-l from the command line before the real parser is built.

    The help texts are translated, so the language must be known first.

    Args:
        argv: Command-line arguments without the program name.

    Returns:
        Optional[str]: The requested language code, or None to auto-detect it.
    """
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("-l", "--lang", choices=["es", "en"], default=None)
    return pre.parse_known_args(argv)[0].lang


def _build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser with help texts in the active language."""
    parser = argparse.ArgumentParser(
        prog="gossip",
        description=_(
            "Gossip: explorer and manager for secrets in Google Cloud Platform, "
            "AWS Secrets Manager, AWS Parameter Store, Azure Key Vault, Ansible Vault, HashiCorp Vault / OpenBao and Kubernetes Secrets"
        ),
    )
    parser.add_argument(
        "-P",
        "--provider",
        choices=list(registry.PROVIDER_IDS),
        default=None,
        help=_(
            "Initial secret provider (gcp, aws, ssm, azure, ansible, vault or k8s; "
            "default: the last one used, otherwise gcp)"
        ),
    )
    for option in registry.all_options():
        names = [option.short, option.flag] if option.short else [option.flag]
        metavar = option.flag[2:].replace("-", "_").upper()
        parser.add_argument(
            *names, dest=option.name, metavar=metavar, help=option.help(), default=None
        )
    parser.add_argument(
        "-l",
        "--lang",
        choices=["es", "en"],
        default=None,
        help=_("Interface language (es, en)"),
    )
    parser.add_argument(
        "-m",
        "--maximized",
        action="store_true",
        help=_("Start the window maximized"),
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help=_("Initial window width in pixels (default: the last one used, otherwise 1280)"),
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help=_("Initial window height in pixels (default: the last one used, otherwise 820)"),
    )
    parser.add_argument(
        "--renderer",
        choices=["ngl", "gl", "vulkan", "cairo"],
        default=None,
        help=_("GTK4 / GSK renderer (GSK_RENDERER: ngl, gl, vulkan, cairo)"),
    )
    parser.add_argument(
        "--software-rendering",
        action="store_true",
        help=_("Force Cairo software rendering (useful in VMs or drivers without 3D acceleration)"),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=_("Write detailed diagnostics to stderr (same as GOSSIP_DEBUG=1)"),
    )
    parser.add_argument(
        "--read-only",
        action="store_true",
        help=_(
            "Browse and copy only (locked for the session): creating, editing, deleting and "
            "importing are disabled"
        ),
    )
    parser.add_argument(
        "--audit-log",
        nargs="?",
        const="1",
        default=None,
        metavar="FILE",
        help=_(
            "Record what is revealed, copied and changed (never the values) in a local file "
            "(default file: audit.jsonl next to the saved state)"
        ),
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=None,
        metavar="DAYS",
        help=_("Flag secrets not changed for this many days (0 disables; default 90)"),
    )
    parser.add_argument(
        "--idle-lock",
        type=int,
        default=None,
        metavar="SECONDS",
        help=_("Seconds of inactivity before secrets are hidden (0 disables; default 300)"),
    )
    parser.add_argument(
        "--reveal-timeout",
        type=int,
        default=None,
        metavar="SECONDS",
        help=_("Seconds a revealed value stays visible (0 keeps it; default 120)"),
    )
    parser.add_argument(
        "--hide-on-blur",
        action="store_true",
        help=_("Hide revealed values when the window loses focus"),
    )
    parser.add_argument("--self-test-module", help=argparse.SUPPRESS)
    parser.add_argument(
        "--self-test",
        action="store_true",
        help=_("Check that all dependencies load correctly and exit (no GUI)"),
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"Gossip {__version__}",
    )
    return parser


def main() -> int:
    """Parse CLI options, configure runtime environment, and launch the application.

    Returns:
        int: Process exit code (0 for clean termination, non-zero on error).
    """
    init_i18n(_preparse_language(sys.argv[1:]) or state.load()["ui"].get("language"))
    args = _build_parser().parse_args()

    if args.read_only:
        os.environ["GOSSIP_READ_ONLY"] = "1"
        os.environ["GOSSIP_READ_ONLY_LOCKED"] = "1"

    if args.audit_log:
        os.environ["GOSSIP_AUDIT_LOG"] = args.audit_log

    if args.stale_days is not None:
        os.environ["GOSSIP_STALE_DAYS"] = str(max(0, args.stale_days))

    if args.debug or os.environ.get("GOSSIP_DEBUG"):
        from src.log import enable_debug, get_logger

        enable_debug()
        get_logger(__name__).debug(
            "Gossip %s on %s, python %s, frozen=%s",
            __version__,
            sys.platform,
            sys.version.split()[0],
            getattr(sys, "frozen", False),
        )

    if args.idle_lock is not None:
        os.environ["GOSSIP_IDLE_LOCK_SECONDS"] = str(args.idle_lock)

    if args.reveal_timeout is not None:
        os.environ["GOSSIP_REVEAL_SECONDS"] = str(max(0, args.reveal_timeout))

    if args.hide_on_blur:
        os.environ["GOSSIP_HIDE_ON_BLUR"] = "1"

    # Configure GTK4 renderer if requested
    if args.software_rendering:
        os.environ["GSK_RENDERER"] = "cairo"
        os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    elif args.renderer:
        os.environ["GSK_RENDERER"] = args.renderer

    if args.self_test_module:
        from src.selftest import check_module

        return check_module(args.self_test_module)

    if args.self_test:
        from src.selftest import run_self_test

        return run_self_test()

    # Validate graphical environment on Linux
    if sys.platform not in ("win32", "darwin"):
        if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
            print(
                _("Error: No display server (X11 or Wayland) detected."),
                file=sys.stderr,
            )
            return 1

    # Launch GTK4/Libadwaita GUI
    from src.ui.app import run_app

    ui = state.load()["ui"]

    return run_app(
        provider=args.provider or state.load()["provider"] or "gcp",
        width=args.width or ui.get("width", state.DEFAULT_WIDTH),
        height=args.height or ui.get("height", state.DEFAULT_HEIGHT),
        maximized=args.maximized or ui.get("maximized", False),
        **{name: getattr(args, name) for name in registry.option_names()},
    )


if __name__ == "__main__":
    sys.exit(main())

__all__ = ["main", "setup_frozen_environment"]
