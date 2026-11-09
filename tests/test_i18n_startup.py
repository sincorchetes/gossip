"""Importing the i18n module must not hide the user's own locale variables."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = (
    "import os\n"
    "import src.i18n as i18n\n"
    "print(repr(os.environ.get('LANGUAGE')), i18n.detect_system_language())\n"
)


class TestStartupLanguage(unittest.TestCase):
    def _probe(self, **env: str) -> str:
        result = subprocess.run(
            [sys.executable, "-c", PROBE],
            cwd=ROOT,
            env={"PATH": "/usr/bin", "PYTHONPATH": str(ROOT), **env},
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def test_lang_alone_selects_english(self):
        # Regression: the import-time default used to export LANGUAGE=es, so LANG was never read.
        self.assertEqual(self._probe(LANG="en_US.UTF-8"), "None en")

    def test_lang_spanish_selects_spanish(self):
        self.assertEqual(self._probe(LANG="es_ES.UTF-8"), "None es")

    def test_user_language_variable_still_wins(self):
        self.assertEqual(self._probe(LANGUAGE="es", LANG="en_US.UTF-8"), "'es' es")


if __name__ == "__main__":
    unittest.main()
