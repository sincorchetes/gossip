"""Gettext compilation and runtime domain binding utilities for Gossip."""

from __future__ import annotations

import locale
import os
import struct
import sys


def _unescape_po_str(s: str) -> str:
    """Unescapes standard PO string escapes while preserving UTF-8 multi-byte characters.

    Args:
        s: Raw string slice from PO file.

    Returns:
        str: Unescaped string content.
    """
    res = []
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "\\" and i + 1 < n:
            c = s[i + 1]
            if c == "n":
                res.append("\n")
                i += 2
            elif c == "t":
                res.append("\t")
                i += 2
            elif c == "r":
                res.append("\r")
                i += 2
            elif c == '"':
                res.append('"')
                i += 2
            elif c == "\\":
                res.append("\\")
                i += 2
            else:
                res.append(c)
                i += 2
        else:
            res.append(s[i])
            i += 1
    return "".join(res)


def compile_po_to_mo(po_file: str, mo_file: str) -> None:
    """Compile a gettext .po file into a binary .mo file using pure Python.

    Args:
        po_file: Filesystem path to the input .po file.
        mo_file: Filesystem path where the binary .mo file will be written.
    """
    if not os.path.exists(po_file):
        return

    if os.path.exists(mo_file) and os.path.getmtime(mo_file) >= os.path.getmtime(po_file):
        return

    messages = {}
    current_msgid = None
    current_msgstr = None
    in_msgid = False
    in_msgstr = False

    with open(po_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines:
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue

        if line_clean.startswith('msgid "'):
            if current_msgid is not None and current_msgstr is not None:
                messages[current_msgid] = current_msgstr
            current_msgid = _unescape_po_str(line_clean[7:-1])
            current_msgstr = None
            in_msgid = True
            in_msgstr = False
        elif line_clean.startswith('msgstr "'):
            current_msgstr = _unescape_po_str(line_clean[8:-1])
            in_msgid = False
            in_msgstr = True
        elif line_clean.startswith('"') and line_clean.endswith('"'):
            unescaped = _unescape_po_str(line_clean[1:-1])
            if in_msgid and current_msgid is not None:
                current_msgid += unescaped
            elif in_msgstr and current_msgstr is not None:
                current_msgstr += unescaped

    if current_msgid is not None and current_msgstr is not None:
        messages[current_msgid] = current_msgstr

    os.makedirs(os.path.dirname(os.path.abspath(mo_file)), exist_ok=True)

    keys = sorted(messages.keys())
    offsets = []
    ids = b""
    strs = b""

    for k in keys:
        v = messages[k]
        k_b = k.encode("utf-8")
        v_b = v.encode("utf-8")
        offsets.append((len(ids), len(k_b), len(strs), len(v_b)))
        ids += k_b + b"\x00"
        strs += v_b + b"\x00"

    key_start = 7 * 4 + len(keys) * 8 * 2
    value_start = key_start + len(ids)

    k_table = []
    v_table = []
    for id_offset, id_len, str_offset, str_len in offsets:
        k_table.extend([id_len, key_start + id_offset])
        v_table.extend([str_len, value_start + str_offset])

    header = struct.pack(
        "Iiiiiii",
        0x950412DE,
        0,
        len(keys),
        7 * 4,
        7 * 4 + len(keys) * 8,
        0,
        0,
    )

    with open(mo_file, "wb") as f:
        f.write(header)
        f.write(struct.pack(f"{len(k_table)}i", *k_table))
        f.write(struct.pack(f"{len(v_table)}i", *v_table))
        f.write(ids)
        f.write(strs)


def get_locale_search_dirs(locale_dir: str | None = None) -> list[str]:
    """Return all candidate directories containing gettext locale message catalogs.

    Args:
        locale_dir: Optional project root locale directory.

    Returns:
        list[str]: Existing filesystem directories where .mo catalogs may reside.
    """
    candidates = []
    if locale_dir:
        candidates.append(locale_dir)

    if getattr(sys, "frozen", False):
        bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
        candidates.append(os.path.join(bundle_dir, "locales"))
        candidates.append(os.path.join(bundle_dir, "share", "locale"))

    for prefix in ("/ucrt64/share/locale", "/usr/share/locale", "/usr/local/share/locale"):
        candidates.append(prefix)

    for var in ("XDG_DATA_DIRS", "GI_TYPELIB_PATH"):
        for entry in os.environ.get(var, "").split(os.pathsep):
            if entry:
                cand = (
                    os.path.join(entry, "locale")
                    if not entry.endswith("girepository-1.0")
                    else os.path.join(os.path.dirname(os.path.dirname(entry)), "share", "locale")
                )
                candidates.append(cand)

    seen = set()
    res = []
    for d in candidates:
        norm = os.path.normpath(d)
        if norm not in seen and os.path.isdir(norm):
            seen.add(norm)
            res.append(norm)
    return res


def bind_domain(domain: str, localedir: str) -> None:
    """Bind a gettext domain to a target directory for both Python and native C libraries.

    Args:
        domain: Gettext domain name string (e.g. 'libadwaita', 'gtk40', 'gossip-gcp').
        localedir: Filesystem path to the root locale directory containing language subfolders.
    """
    if hasattr(locale, "bindtextdomain"):
        try:
            locale.bindtextdomain(domain, localedir)
        except Exception:
            pass
    if hasattr(locale, "bind_textdomain_codeset"):
        try:
            locale.bind_textdomain_codeset(domain, "UTF-8")
        except Exception:
            pass

    try:
        import ctypes

        for libname in ("libintl-8.dll", "libintl.dll", "libc.so.6", None):
            try:
                c_lib = ctypes.cdll.LoadLibrary(libname) if libname else ctypes.CDLL(None)
                if hasattr(c_lib, "bindtextdomain"):
                    c_lib.bindtextdomain.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                    c_lib.bindtextdomain.restype = ctypes.c_char_p
                    c_lib.bindtextdomain(domain.encode("utf-8"), localedir.encode("utf-8"))
                if hasattr(c_lib, "bind_textdomain_codeset"):
                    c_lib.bind_textdomain_codeset.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
                    c_lib.bind_textdomain_codeset.restype = ctypes.c_char_p
                    c_lib.bind_textdomain_codeset(domain.encode("utf-8"), b"UTF-8")
                break
            except Exception:
                continue
    except Exception:
        pass
