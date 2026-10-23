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

# In Windows GUI / PyInstaller --windowed environments, standard streams are None.
# Provide null writers to prevent AttributeError: 'NoneType' object has no attribute 'write'.
if sys.stdout is None:  # pragma: no cover
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:  # pragma: no cover
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure src is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import __version__
from src.i18n import _, init_i18n


def setup_frozen_environment() -> None:
    """Configure GObject Introspection typelib, schema, and DLL paths when frozen.

    Ensures that PyInstaller standalone bundles find bundled or system-level
    typelibs (Gtk-4.0, Adw-1, etc.), GLib schemas, and required shared libraries
    across Linux, Windows, and macOS distributions.
    """
    if getattr(sys, "frozen", False):
        real_exe = os.path.realpath(sys.executable)
        exe_dir = os.path.dirname(real_exe)
        bundle_dir = getattr(sys, "_MEIPASS", exe_dir)

        base_dirs: list[str] = []
        for candidate in [bundle_dir, exe_dir, os.path.join(exe_dir, "_internal")]:
            if candidate and os.path.isdir(candidate) and candidate not in base_dirs:
                base_dirs.append(candidate)
        if not base_dirs:
            base_dirs = [exe_dir]

        if sys.platform == "win32":
            if hasattr(os, "add_dll_directory") and os.path.isdir(bundle_dir):
                try:
                    os.add_dll_directory(bundle_dir)
                except Exception:
                    pass
            current_path = os.environ.get("PATH", "")
            os.environ["PATH"] = bundle_dir + (os.pathsep + current_path if current_path else "")

            # Ensure POSIX shims are active on Windows for Ansible Core
            from src.providers.ansible import install_posix_shims

            install_posix_shims()

        typelib_candidates: list[str] = []
        for b in base_dirs:
            typelib_candidates.extend(
                [
                    os.path.join(b, "gi_typelibs"),
                    os.path.join(b, "girepository-1.0"),
                    os.path.join(b, "lib", "girepository-1.0"),
                ]
            )
        typelib_candidates.extend(
            [
                "/usr/lib64/girepository-1.0",
                "/usr/lib/x86_64-linux-gnu/girepository-1.0",
                "/usr/lib/aarch64-linux-gnu/girepository-1.0",
                "/usr/lib/girepository-1.0",
                "/usr/local/lib64/girepository-1.0",
                "/usr/local/lib/girepository-1.0",
            ]
        )
        existing_typelibs = [p for p in dict.fromkeys(typelib_candidates) if os.path.isdir(p)]
        if existing_typelibs:
            current_env = os.environ.get("GI_TYPELIB_PATH", "")
            all_paths = existing_typelibs + ([current_env] if current_env else [])
            os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(all_paths)

            # Dynamically register search paths directly into live C GObject Introspection repository
            try:
                import gi  # noqa: F401
                from gi._gi import Repository

                repo = Repository.get_default()
                for p in reversed(existing_typelibs):
                    repo.prepend_search_path(p)
            except Exception:
                pass

        schema_candidates: list[str] = []
        for b in base_dirs:
            schema_candidates.extend(
                [
                    os.path.join(b, "glib-2.0", "schemas"),
                    os.path.join(b, "share", "glib-2.0", "schemas"),
                ]
            )
        schema_candidates.extend(
            [
                "/usr/share/glib-2.0/schemas",
                "/usr/local/share/glib-2.0/schemas",
            ]
        )
        existing_schemas = [p for p in dict.fromkeys(schema_candidates) if os.path.isdir(p)]
        if existing_schemas:
            current_schema = os.environ.get("GSETTINGS_SCHEMA_DIR", "")
            all_schemas = existing_schemas + ([current_schema] if current_schema else [])
            os.environ["GSETTINGS_SCHEMA_DIR"] = os.pathsep.join(all_schemas)

        xdg_candidates: list[str] = []
        for b in base_dirs:
            xdg_candidates.extend(
                [
                    os.path.join(b, "share"),
                    b,
                ]
            )
        xdg_candidates.extend(
            [
                "/usr/share",
                "/usr/local/share",
            ]
        )
        existing_xdg = [p for p in dict.fromkeys(xdg_candidates) if os.path.isdir(p)]
        if existing_xdg:
            current_xdg = os.environ.get("XDG_DATA_DIRS", "")
            all_xdg = existing_xdg + ([current_xdg] if current_xdg else [])
            os.environ["XDG_DATA_DIRS"] = os.pathsep.join(all_xdg)


setup_frozen_environment()


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
        "-P",
        "--provider",
        choices=["gcp", "aws", "azure", "ansible"],
        default="gcp",
        help="Proveedor inicial de secretos (gcp, aws, azure o ansible, por defecto: gcp)",
    )
    parser.add_argument(
        "-p",
        "--project",
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
        "-l",
        "--lang",
        choices=["es", "en"],
        default=None,
        help="Idioma de la interfaz / UI language (es, en)",
    )
    parser.add_argument(
        "-m",
        "--maximized",
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
        "--renderer",
        choices=["ngl", "gl", "vulkan", "cairo"],
        default=None,
        help="Motor de renderizado GTK4 / GSK (GSK_RENDERER: ngl, gl, vulkan, cairo)",
    )
    parser.add_argument(
        "--software-rendering",
        action="store_true",
        help="Fuerza renderizado por software Cairo (útil en VMs o drivers sin aceleración 3D)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"Gossip {__version__}",
    )

    args = parser.parse_args()

    # Configure GTK4 renderer if requested
    if args.software_rendering:
        os.environ["GSK_RENDERER"] = "cairo"
        os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
    elif args.renderer:
        os.environ["GSK_RENDERER"] = args.renderer

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
