from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import make_license_rtf as mlr  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestMarkdownToRtf(unittest.TestCase):
    def test_document_structure(self):
        rtf = mlr.markdown_to_rtf("# TITLE\nbody")
        self.assertTrue(rtf.startswith("{\\rtf1"))
        self.assertTrue(rtf.rstrip().endswith("}"))
        self.assertIn("TITLE\\par", rtf)
        self.assertNotIn("# TITLE", rtf)

    def test_code_fences_are_dropped(self):
        self.assertNotIn("```", mlr.markdown_to_rtf("```\ntext\n```"))

    def test_rtf_control_characters_are_escaped(self):
        rtf = mlr.markdown_to_rtf("a\\b {c} d")
        self.assertIn("a\\\\b \\{c\\} d", rtf)

    def test_non_ascii_becomes_unicode_escapes(self):
        rtf = mlr.markdown_to_rtf("año — 😀")
        self.assertIn("a\\u241?o", rtf)
        self.assertIn("\\u8212?", rtf)
        self.assertTrue(rtf.isascii())

    def test_tabs(self):
        self.assertIn("\\tab ", mlr.markdown_to_rtf("a\tb"))

    def test_real_license_converts_to_ascii_rtf(self):
        with open(os.path.join(ROOT, "LICENSE.md"), encoding="utf-8") as handle:
            rtf = mlr.markdown_to_rtf(handle.read())
        self.assertTrue(rtf.isascii())
        self.assertIn("GNU GENERAL PUBLIC LICENSE", rtf)

    def test_main_writes_file_and_validates_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "out", "LICENSE.rtf")
            self.assertEqual(mlr.main(["x", os.path.join(ROOT, "LICENSE.md"), target]), 0)
            with open(target, encoding="ascii") as handle:
                self.assertTrue(handle.read().startswith("{\\rtf1"))
        self.assertEqual(mlr.main(["x"]), 2)


if __name__ == "__main__":
    unittest.main()
