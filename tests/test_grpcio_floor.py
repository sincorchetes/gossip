from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import check_grpcio_floor as cgf  # noqa: E402


class TestGrpcioFloor(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(cgf.parse_version("1.82.0"), (1, 82))
        self.assertEqual(cgf.parse_version("1.84.1rc1"), (1, 84))
        with self.assertRaises(ValueError):
            cgf.parse_version("unknown")

    def test_new_enough_versions_are_ok_on_any_date(self):
        for today in (date(2026, 10, 26), date(2027, 2, 1), date(2028, 1, 1)):
            self.assertEqual(cgf.evaluate("1.83.0", today)[0], "ok")
            self.assertEqual(cgf.evaluate("2.0.0", today)[0], "ok")

    def test_old_version_is_silent_then_warns_then_fails(self):
        self.assertEqual(cgf.evaluate("1.82.0", date(2026, 12, 31))[0], "ok")
        self.assertEqual(cgf.evaluate("1.82.0", date(2027, 1, 1))[0], "warning")
        self.assertEqual(cgf.evaluate("1.82.0", date(2027, 3, 31))[0], "warning")
        self.assertEqual(cgf.evaluate("1.82.0", date(2027, 4, 1))[0], "error")

    def _run(self, argv, today):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cgf.main(argv, today)
        return code, out.getvalue()

    def test_main_prints_github_annotations_and_exit_codes(self):
        code, text = self._run(["x", "1.82.0"], date(2027, 2, 1))
        self.assertEqual((code, text.startswith("::warning::")), (0, True))
        code, text = self._run(["x", "1.82.0"], date(2027, 5, 1))
        self.assertEqual((code, text.startswith("::error::")), (1, True))
        code, text = self._run(["x", "1.85.0"], date(2027, 5, 1))
        self.assertEqual((code, text.startswith("::")), (0, False))

    def test_main_reads_the_installed_version_by_default(self):
        code, text = self._run(["x"], date(2026, 10, 26))
        self.assertEqual(code, 0)
        self.assertIn("grpcio", text)


if __name__ == "__main__":
    unittest.main()
