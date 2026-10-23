"""Internationalization and localization module with pure-Python gettext compilation."""

from __future__ import annotations

import gettext
import locale
import os
from typing import Optional

from src.i18n_compiler import (
    _unescape_po_str,
    bind_domain,
    compile_po_to_mo,
)
from src.i18n_compiler import (
    get_locale_search_dirs as _get_locale_search_dirs,
)

DOMAIN = "gossip-gcp"
LOCALE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "locales")

SUPPORTED_LANGUAGES = {
    "es": "Español",
    "en": "English",
}

_current_lang = "es"
_current_translation: gettext.NullTranslations = gettext.NullTranslations()


def get_locale_search_dirs() -> list[str]:
    """Return all candidate directories containing gettext locale message catalogs.

    Returns:
        list[str]: Existing filesystem directories where .mo catalogs may reside.
    """
    return _get_locale_search_dirs(LOCALE_DIR)


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

__all__ = [
    "DOMAIN",
    "LOCALE_DIR",
    "SUPPORTED_LANGUAGES",
    "_",
    "_unescape_po_str",
    "bind_domain",
    "compile_po_to_mo",
    "configure_system_locale",
    "detect_system_language",
    "ensure_mo_compiled",
    "get_current_language",
    "get_locale_search_dirs",
    "init_i18n",
    "set_language",
]
