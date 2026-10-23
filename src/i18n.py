"""Internationalization and localization module with pure-Python gettext compilation."""

from __future__ import annotations

import gettext
import locale
import os
import struct
import sys
from typing import Dict, Optional

DOMAIN = "gossip-gcp"
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")

SUPPORTED_LANGUAGES = {
    "es": "Español",
    "en": "English",
}

_current_lang = "es"
_current_translation: gettext.NullTranslations = gettext.NullTranslations()


def _unescape_po_str(s: str) -> str:
    """Unescapes standard PO string escapes while preserving UTF-8 multi-byte characters."""
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

    # If mo exists and is newer than po, skip
    if os.path.exists(mo_file) and os.path.getmtime(mo_file) >= os.path.getmtime(po_file):
        return

    lines = []
    with open(po_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    messages: Dict[str, str] = {}
    msgid = None
    msgstr = None
    in_msgid = False
    in_msgstr = False

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            if msgid is not None and msgstr is not None:
                messages[msgid] = msgstr
                msgid = None
                msgstr = None
                in_msgid = False
                in_msgstr = False
            continue

        if line.startswith('msgid "'):
            if msgid is not None and msgstr is not None:
                messages[msgid] = msgstr
            msgid = _unescape_po_str(line[7:-1])
            msgstr = ""
            in_msgid = True
            in_msgstr = False
        elif line.startswith('msgstr "'):
            msgstr = _unescape_po_str(line[8:-1])
            in_msgid = False
            in_msgstr = True
        elif line.startswith('"') and line.endswith('"'):
            val = _unescape_po_str(line[1:-1])
            if in_msgid and msgid is not None:
                msgid += val
            elif in_msgstr and msgstr is not None:
                msgstr += val

    if msgid is not None and msgstr is not None:
        messages[msgid] = msgstr

    # Generate MO binary
    os.makedirs(os.path.dirname(mo_file), exist_ok=True)
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

    # Magic number 0x950412de, revision 0, N keys
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


def get_locale_search_dirs() -> list[str]:
    """Return all candidate directories containing gettext locale message catalogs.

    Returns:
        list[str]: Existing filesystem directories where .mo catalogs may reside.
    """
    candidates = [LOCALE_DIR]

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


def configure_system_locale(lang: str) -> None:
    """Synchronize environment variables and C runtime locale for the active language.

    Args:
        lang: Target two-letter language identifier (e.g. 'es' or 'en').
    """
    os.environ["LANGUAGE"] = lang
    if lang == "es":
        candidates = ("es_ES.UTF-8", "es_ES.utf8", "es_ES", "es", "Spanish_Spain.1252", "Spanish")
    else:
        candidates = ("en_US.UTF-8", "en_US.utf8", "en_US", "en", "C.UTF-8", "C")

    for loc in candidates:
        try:
            locale.setlocale(locale.LC_ALL, loc)
            break
        except Exception:
            pass

    try:
        from gi.repository import GLib

        GLib.setenv("LANGUAGE", lang, True)
    except Exception:
        pass

    locale_dirs = get_locale_search_dirs()
    for domain in ("gossip-gcp", "libadwaita", "gtk40"):
        for ldir in locale_dirs:
            bind_domain(domain, ldir)


def ensure_mo_compiled() -> None:
    """Ensure all supported language .po catalog files have up-to-date compiled .mo binaries."""
    for lang in SUPPORTED_LANGUAGES.keys():
        po_path = os.path.join(LOCALE_DIR, lang, "LC_MESSAGES", f"{DOMAIN}.po")
        mo_path = os.path.join(LOCALE_DIR, lang, "LC_MESSAGES", f"{DOMAIN}.mo")
        if os.path.exists(po_path):
            compile_po_to_mo(po_path, mo_path)


def detect_system_language() -> str:
    """Detect the host system language from standard environment variables in priority order.

    Checks LANGUAGE, LC_ALL, LC_MESSAGES, and LANG.

    Returns:
        str: Detected language code ('es' or 'en', defaulting to 'es').
    """
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.getenv(var, "").strip()
        if val:
            for part in val.split(":"):
                part = part.strip().lower()
                if part.startswith("es"):
                    return "es"
                if part.startswith("en"):
                    return "en"
    return "es"


def init_i18n(preferred_lang: Optional[str] = None) -> None:
    """Initialize the gettext translation system with the specified or detected language.

    Args:
        preferred_lang: Explicit language code ('es' or 'en'). If None, detects system language.
    """
    global _current_lang, _current_translation

    ensure_mo_compiled()

    # Detect language if not explicitly provided
    lang = preferred_lang or detect_system_language()

    if lang not in SUPPORTED_LANGUAGES:
        lang = "es"

    _current_lang = lang
    configure_system_locale(lang)

    try:
        _current_translation = gettext.translation(
            domain=DOMAIN,
            localedir=LOCALE_DIR,
            languages=[lang],
            fallback=True,
        )
    except Exception:
        _current_translation = gettext.NullTranslations()


def set_language(lang: str) -> None:
    """Switch the currently active application language at runtime.

    Args:
        lang: Target language code ('es' or 'en').
    """
    init_i18n(lang)


def get_current_language() -> str:
    """Return the active two-letter language code (e.g., 'es' or 'en').

    Returns:
        str: Currently active language code.
    """
    return _current_lang


def _(message: str) -> str:
    """Translate a gettext message string into the active locale.

    Args:
        message: Original English message string.

    Returns:
        str: Translated message string, or original message if translation is unavailable.
    """
    return _current_translation.gettext(message)


# Initialize default Spanish localization on module import
init_i18n("es")
