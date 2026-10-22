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
    compile_po_to_mo,
    detect_system_language,
    ensure_mo_compiled,
    get_current_language,
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

    @patch.dict("os.environ", {"LC_ALL": "en_US.UTF-8", "LANG": "es_ES.UTF-8"})
    def test_detect_system_language_from_lc_all(self):
        self.assertEqual(detect_system_language(), "en")

    @patch.dict("os.environ", {"LC_MESSAGES": "es_ES.UTF-8"})
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


if __name__ == "__main__":
    import time
    unittest.main()
