from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "generate_icons.sh")
PNG_MAGIC = b"\x89PNG"
HAS_RENDERER = any(shutil.which(t) for t in ("rsvg-convert", "inkscape"))


@unittest.skipIf(
    sys.platform == "win32" or shutil.which("bash") is None or not HAS_RENDERER,
    "needs bash and rsvg-convert or inkscape",
)
class TestGenerateIcons(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.out.cleanup()

    def _generate(self, fmt):
        path = os.path.join(self.out.name, f"icon.{fmt}")
        result = subprocess.run(["bash", SCRIPT, fmt, path], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(path, "rb") as f:
            return f.read()

    def test_icns_is_well_formed_with_png_entries(self):
        data = self._generate("icns")
        self.assertEqual(data[:4], b"icns")
        self.assertEqual(struct.unpack(">I", data[4:8])[0], len(data))
        pos, kinds = 8, []
        while pos < len(data):
            kind = data[pos : pos + 4].decode()
            length = struct.unpack(">I", data[pos + 4 : pos + 8])[0]
            self.assertEqual(data[pos + 8 : pos + 12], PNG_MAGIC)
            kinds.append(kind)
            pos += length
        self.assertEqual(pos, len(data))
        self.assertIn("ic10", kinds)  # 1024 px (512@2x)

    def test_ico_has_all_sizes_with_png_payloads(self):
        data = self._generate("ico")
        reserved, kind, count = struct.unpack("<HHH", data[:6])
        self.assertEqual((reserved, kind, count), (0, 1, 7))
        offset = struct.unpack("<I", data[6 + 12 : 6 + 16])[0]
        self.assertEqual(data[offset : offset + 4], PNG_MAGIC)

    def test_unknown_format_is_rejected(self):
        result = subprocess.run(
            ["bash", SCRIPT, "bmp", os.path.join(self.out.name, "x")],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
