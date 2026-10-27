"""Runtime bootstrap and environment initialization for Gossip."""

from __future__ import annotations

import os
import sys


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

            # Provide the Unix-only modules and valid std streams that Ansible Core expects
            from src.providers.ansible.compat import ensure_windows_runtime

            ensure_windows_runtime()

        if sys.platform == "darwin":
            frameworks_dir = os.path.join(exe_dir, "..", "Frameworks")
            macos_lib_dirs = [
                exe_dir,
                bundle_dir,
                frameworks_dir,
                "/usr/local/lib",
                "/opt/homebrew/lib",
            ]
            existing_lib_dirs = [d for d in macos_lib_dirs if os.path.isdir(d)]
            if existing_lib_dirs:
                cur_dyld = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
                os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = os.pathsep.join(
                    existing_lib_dirs + ([cur_dyld] if cur_dyld else [])
                )

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

        # Ensure GdkPixbuf has access to an SVG-capable loaders.cache
        pixbuf_cache = os.environ.get("GDK_PIXBUF_MODULE_FILE")
        needs_system_pixbuf = True
        if pixbuf_cache and os.path.isfile(pixbuf_cache):
            try:
                with open(pixbuf_cache, "r", encoding="utf-8", errors="ignore") as f:
                    if "svg" in f.read():
                        needs_system_pixbuf = False
            except Exception:
                pass
        if needs_system_pixbuf:
            for sys_cache in [
                "/usr/lib64/gdk-pixbuf-2.0/2.10.0/loaders.cache",
                "/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache",
                "/usr/lib/aarch64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache",
                "/usr/lib/gdk-pixbuf-2.0/2.10.0/loaders.cache",
            ]:
                if os.path.isfile(sys_cache):
                    try:
                        with open(sys_cache, "r", encoding="utf-8", errors="ignore") as f:
                            if "svg" in f.read():
                                os.environ["GDK_PIXBUF_MODULE_FILE"] = sys_cache
                                break
                    except Exception:
                        pass
