from __future__ import annotations

import os
import tempfile
import time
import unittest
from unittest.mock import patch

from src.i18n import (
    _,
    SUPPORTED_LANGUAGES,
    _unescape_po_str,
    bind_domain,
    compile_po_to_mo,
    configure_system_locale,
    detect_system_language,
    ensure_mo_compiled,
    get_current_language,
    get_locale_search_dirs,
    init_i18n,
    set_language,
)


class TestI18n(unittest.TestCase):
    def setUp(self):
        init_i18n("es")

    def test_supported_languages(self):
        self.assertIn("es", SUPPORTED_LANGUAGES)
        self.assertIn("en", SUPPORTED_LANGUAGES)

    def test_switch_language(self):
        set_language("en")
        self.assertEqual(get_current_language(), "en")
        english_trans = _("Gossip")
        self.assertEqual(english_trans, "Gossip")

        set_language("es")
        self.assertEqual(get_current_language(), "es")

    @patch.dict("os.environ", {"LANGUAGE": "es_ES:es"})
    def test_detect_system_language_from_language_var(self):
        self.assertEqual(detect_system_language(), "es")

    @patch.dict("os.environ", {"LC_ALL": "en_US.UTF-8", "LANG": "es_ES.UTF-8", "LANGUAGE": ""})
    def test_detect_system_language_from_lc_all(self):
        self.assertEqual(detect_system_language(), "en")

    @patch.dict("os.environ", {"LC_MESSAGES": "es_ES.UTF-8", "LC_ALL": "", "LANGUAGE": ""})
    def test_detect_system_language_from_lc_messages(self):
        self.assertEqual(detect_system_language(), "es")

    @patch.dict("os.environ", {"LANG": "fr_FR.UTF-8", "LC_ALL": "", "LC_MESSAGES": "", "LANGUAGE": ""})
    def test_detect_system_language_unsupported_fallback(self):
        self.assertEqual(detect_system_language(), "es")

    def test_unknown_language_fallback(self):
        init_i18n("de")
        self.assertEqual(get_current_language(), "es")

    def test_unescape_po_str(self):
        raw = r'Hello\nWorld\t\"Escaped\"\r\\Done\x'
        unescaped = _unescape_po_str(raw)
        self.assertEqual(unescaped, 'Hello\nWorld\t"Escaped"\r\\Donex')

    def test_compile_po_to_mo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            po_file = os.path.join(tmpdir, "test.po")
            mo_file = os.path.join(tmpdir, "test.mo")

            po_content = """# Comment line
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

msgid "Hello"
msgstr "Hola"

msgid "Goodbye"
msgstr "Adiós"

msgid "Multiline"
" Key"
msgstr "Multi"
"línea"
"""
            with open(po_file, "w", encoding="utf-8") as f:
                f.write(po_content)

            # Test compilation
            compile_po_to_mo(po_file, mo_file)
            self.assertTrue(os.path.exists(mo_file))

            # Test skipping if mo is newer than po
            compile_po_to_mo(po_file, mo_file)

            # Test consecutive msgid without blank line
            consecutive_po = """
msgid "first"
msgstr "primer"
msgid "second"
msgstr "segundo"
"""
            with open(po_file, "w", encoding="utf-8") as f:
                f.write(consecutive_po)
            # Make po newer than mo
            os.utime(po_file, (time.time() + 10, time.time() + 10))
            compile_po_to_mo(po_file, mo_file)

            # Test nonexistent po file
            compile_po_to_mo("/nonexistent/path/fake.po", "/nonexistent/path/fake.mo")

            # Test edge cases:
            # - orphaned quoted string when neither in_msgid nor in_msgstr (98->72)
            # - unknown keyword / line starting with " but not ending with " (94->72)
            # - trailing comment at EOF leaving msgid as None (101->105)
            edge_po = """
"orphaned string at start"
unrecognized_keyword_or_tag
msgid "single"
msgstr "simple"

# Trailing comment
"""
            with open(po_file, "w", encoding="utf-8") as f:
                f.write(edge_po)
            os.utime(po_file, (time.time() + 20, time.time() + 20))
            compile_po_to_mo(po_file, mo_file)

    def test_ensure_mo_compiled(self):
        with patch("os.path.exists", return_value=False):
            ensure_mo_compiled()
        ensure_mo_compiled()

    @patch("gettext.translation", side_effect=Exception("Translation file error"))
    def test_init_i18n_translation_exception_fallback(self, mock_gettext):
        init_i18n("es")

    def test_get_locale_search_dirs(self):
        import sys
        # 1. Standard execution
        dirs = get_locale_search_dirs()
        self.assertIsInstance(dirs, list)

        # 2. Frozen with bundle dirs and custom environment variables
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_locales = os.path.join(tmpdir, "locales")
            bundle_share_locale = os.path.join(tmpdir, "share", "locale")
            xdg_locale = os.path.join(tmpdir, "xdg", "locale")
            girepo_dir = os.path.join(tmpdir, "opt", "lib", "girepository-1.0")
            girepo_share_locale = os.path.join(tmpdir, "opt", "share", "locale")
            for d in (bundle_locales, bundle_share_locale, xdg_locale, girepo_dir, girepo_share_locale):
                os.makedirs(d, exist_ok=True)

            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "_MEIPASS", tmpdir, create=True):
                    with patch.dict(os.environ, {
                        "XDG_DATA_DIRS": os.path.join(tmpdir, "xdg"),
                        "GI_TYPELIB_PATH": girepo_dir,
                    }):
                        res = get_locale_search_dirs()
                        self.assertIn(bundle_locales, res)
                        self.assertIn(bundle_share_locale, res)
                        self.assertIn(xdg_locale, res)
                        self.assertIn(girepo_share_locale, res)

    def test_bind_domain(self):
        from unittest.mock import MagicMock
        import locale
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Standard execution
            bind_domain("gossip-gcp", tmpdir)

            # 2. When locale functions exist and succeed
            with patch.object(locale, "bindtextdomain", create=True) as mock_btd, \
                 patch.object(locale, "bind_textdomain_codeset", create=True) as mock_btc:
                bind_domain("gossip-gcp", tmpdir)
                mock_btd.assert_called_with("gossip-gcp", tmpdir)
                mock_btc.assert_called_with("gossip-gcp", "UTF-8")

            # 3. When locale functions raise exceptions
            with patch.object(locale, "bindtextdomain", side_effect=Exception("error"), create=True):
                with patch.object(locale, "bind_textdomain_codeset", side_effect=Exception("error"), create=True):
                    bind_domain("gossip-gcp", tmpdir)

            # 4. When locale does not have bindtextdomain or bind_textdomain_codeset
            real_hasattr = hasattr
            def mock_hasattr(obj, name):
                if obj is locale and name in ("bindtextdomain", "bind_textdomain_codeset"):
                    return False
                return real_hasattr(obj, name)

            with patch("builtins.hasattr", side_effect=mock_hasattr):
                bind_domain("gossip-gcp", tmpdir)

            # 5. When ctypes library loaders raise exceptions
            with patch("ctypes.cdll.LoadLibrary", side_effect=Exception("no lib")):
                with patch("ctypes.CDLL", side_effect=Exception("no cdll")):
                    bind_domain("gossip-gcp", tmpdir)

            # 6. ctypes mock c_lib with attributes
            mock_clib = MagicMock()
            with patch("ctypes.cdll.LoadLibrary", return_value=mock_clib):
                bind_domain("gossip-gcp", tmpdir)
                self.assertTrue(mock_clib.bindtextdomain.called or mock_clib.bind_textdomain_codeset.called)

            # 7. ctypes c_lib without attributes
            dummy_clib = object()
            with patch("ctypes.cdll.LoadLibrary", return_value=dummy_clib):
                bind_domain("gossip-gcp", tmpdir)

            # 8. Exception in ctypes block
            with patch.dict("sys.modules", {"ctypes": None}):
                bind_domain("gossip-gcp", tmpdir)

    def test_configure_system_locale(self):
        import locale
        # 1. es
        configure_system_locale("es")
        self.assertEqual(os.environ.get("LANGUAGE"), "es")

        # 2. en
        configure_system_locale("en")
        self.assertEqual(os.environ.get("LANGUAGE"), "en")

        # 3. Mock setlocale raising exception on some candidates
        real_setlocale = locale.setlocale
        def mock_setlocale(cat, loc):
            if "UTF-8" in loc or "utf8" in loc:
                raise Exception("unsupported locale")
            return real_setlocale(cat, loc)

        with patch("locale.setlocale", side_effect=mock_setlocale):
            configure_system_locale("es")

        # 4. GLib.setenv raising exception
        with patch("gi.repository.GLib.setenv", side_effect=Exception("glib fail")):
            configure_system_locale("es")


if __name__ == "__main__":
    import time
    unittest.main()
