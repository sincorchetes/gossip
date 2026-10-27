from __future__ import annotations

import unittest

from src.clipboard import SENSITIVE_FORMATS, secret_content


class TestSecretContent(unittest.TestCase):
    def test_offers_the_text_and_every_do_not_record_hint(self):
        provider = secret_content("hunter2")
        formats = provider.ref_formats().to_string()
        self.assertIn("gchararray", formats)  # serialised as text by GTK
        for mime in SENSITIVE_FORMATS:
            self.assertIn(mime, formats)

    def test_hints_cover_linux_macos_and_windows(self):
        self.assertIn("x-kde-passwordManagerHint", SENSITIVE_FORMATS)
        self.assertIn("org.nspasteboard.ConcealedType", SENSITIVE_FORMATS)
        self.assertIn("ExcludeClipboardContentFromMonitorProcessing", SENSITIVE_FORMATS)
        self.assertIn("CanIncludeInClipboardHistory", SENSITIVE_FORMATS)


if __name__ == "__main__":
    unittest.main()
