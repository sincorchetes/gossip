from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "set_version.sh")


@unittest.skipIf(sys.platform == "win32" or shutil.which("bash") is None, "needs bash and perl")
class TestSetVersion(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.root.name, "src"))
        with open(os.path.join(self.root.name, "src", "__init__.py"), "w") as f:
            f.write('"""doc"""\n\n__version__ = "0.3.0"\n')
        with open(os.path.join(self.root.name, "pyproject.toml"), "w") as f:
            f.write(
                '[project]\nname = "gossip"\nversion = "0.3.0"\n\n[tool.x]\nversion = "9.9.9"\n'
            )

    def tearDown(self):
        self.root.cleanup()

    def _run(self, version):
        return subprocess.run(
            ["bash", SCRIPT, version, self.root.name], capture_output=True, text=True
        )

    def _read(self, *parts):
        with open(os.path.join(self.root.name, *parts)) as f:
            return f.read()

    def test_stamps_tag_without_v_prefix(self):
        result = self._run("v0.3.42")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('__version__ = "0.3.42"', self._read("src", "__init__.py"))

    def test_only_first_pyproject_version_changes(self):
        self._run("1.2.3")
        content = self._read("pyproject.toml")
        self.assertIn('name = "gossip"\nversion = "1.2.3"', content)
        self.assertIn('[tool.x]\nversion = "9.9.9"', content)

    def test_rejects_invalid_version_and_leaves_files_untouched(self):
        for bad in ("main", "abcdef12", '1.0"; rm -rf /', ""):
            result = self._run(bad)
            self.assertNotEqual(result.returncode, 0)
        self.assertIn('__version__ = "0.3.0"', self._read("src", "__init__.py"))


if __name__ == "__main__":
    unittest.main()
