from __future__ import annotations

import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMMON = os.path.join(ROOT, "packaging", "pyinstaller-common.sh")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "release.yml")


@unittest.skipIf(shutil.which("bash") is None, "needs bash")
class TestPyInstallerCommonArgs(unittest.TestCase):
    def _common_args(self):
        out = subprocess.run(
            ["bash", "-c", f'source "{COMMON}"; printf "%s\\n" "${{PYI_COMMON_ARGS[@]}}"'],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return out.splitlines()

    def test_common_args_contain_the_shared_build_options(self):
        args = self._common_args()
        for expected in ("--noconfirm", "--onedir", "--windowed", "gossip", "gi"):
            self.assertIn(expected, args)
        hidden = [a for i, a in enumerate(args) if i and args[i - 1] == "--hidden-import"]
        self.assertTrue({"gi.repository.Gtk", "gi.repository.Adw"} <= set(hidden))
        excluded = [a for i, a in enumerate(args) if i and args[i - 1] == "--exclude-module"]
        self.assertEqual(len(excluded), 4)

    def test_every_platform_build_uses_the_shared_options(self):
        with open(WORKFLOW) as f:
            workflow = f.read()
        self.assertEqual(workflow.count("source packaging/pyinstaller-common.sh"), 3)
        self.assertEqual(workflow.count('pyinstaller "${PYI_COMMON_ARGS[@]}"'), 3)
        self.assertIsNone(re.search(r"pyinstaller --noconfirm", workflow))


if __name__ == "__main__":
    unittest.main()
