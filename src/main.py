"""Main entry point for the Gossip multi-cloud secret manager CLI and GUI."""

from __future__ import annotations

import argparse
import os
import sys

# Ensure UTF-8 mode and safe environment defaults across operating systems
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("LANG", "C.UTF-8")
os.environ.setdefault("LC_ALL", "C.UTF-8")

# Ensure src is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import __version__
from src.i18n import init_i18n, _


def main() -> int:
    """Parse CLI options, configure runtime environment, and launch the application.

    Returns:
        int: Process exit code (0 for clean termination, non-zero on error).
    """
    parser = argparse.ArgumentParser(
        prog="gossip",
        description="Gossip: Explorador y gestor de secretos en Google Cloud Platform, AWS Secrets Manager, Azure Key Vault y Ansible Vault",
    )
    parser.add_argument(
        "-P", "--provider",
        choices=["gcp", "aws", "azure", "ansible"],
        default="gcp",
        help="Proveedor inicial de secretos (gcp, aws, azure o ansible, por defecto: gcp)",
    )
    parser.add_argument(
        "-p", "--project",
        help="ID del proyecto de GCP a consultar (omite la autodetección)",
        default=None,
    )
    parser.add_argument(
        "--aws-profile",
        help="Perfil de credenciales de AWS a utilizar (omite la autodetección)",
        default=None,
    )
    parser.add_argument(
        "--aws-region",
        help="Región de AWS a consultar (e.g. eu-west-1, us-east-1)",
        default=None,
    )
    parser.add_argument(
        "--azure-vault",
        help="Nombre o URL del almacén Azure Key Vault (omite la autodetección)",
        default=None,
    )
    parser.add_argument(
        "--ansible-vault",
        help="Ruta al archivo cifrado de Ansible Vault (omite la autodetección)",
        default=None,
    )
    parser.add_argument(
        "--ansible-password-file",
        help="Ruta al archivo de contraseña de Ansible Vault (.vault_pass)",
        default=None,
    )
    parser.add_argument(
        "-l", "--lang",
        choices=["es", "en"],
        default=None,
        help="Idioma de la interfaz / UI language (es, en)",
    )
    parser.add_argument(
        "-m", "--maximized",
        action="store_true",
        help="Inicia la ventana gráfica maximizada",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Ancho inicial de la ventana en píxeles (por defecto: 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=820,
        help="Alto inicial de la ventana en píxeles (por defecto: 820)",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"Gossip {__version__}",
    )

    args = parser.parse_args()

    # Initialize localization
    init_i18n(args.lang)

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
    return run_app(
        provider=args.provider,
        project_id=args.project,
        aws_profile=args.aws_profile,
        aws_region=args.aws_region,
        azure_vault=args.azure_vault,
        ansible_vault=args.ansible_vault,
        ansible_password_file=args.ansible_password_file,
        width=args.width,
        height=args.height,
        maximized=args.maximized,
    )


if __name__ == "__main__":
    sys.exit(main())
