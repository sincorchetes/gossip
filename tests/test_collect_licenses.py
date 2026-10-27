from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import macho_utils as mu  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
BASH = shutil.which("bash") or "bash"


def _write_executable(path: Path, body: str) -> None:
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@unittest.skipIf(sys.platform == "win32", "needs bash")
class TestLinuxCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.bundle = self.root / "bundle" / "_internal"
        self.bundle.mkdir(parents=True)
        for name in (
            "libgtk-4.so.1",
            "libglib-2.0.so.0",
            "libpython3.14.so",
            "_cffi.cpython-314.so",
        ):
            (self.bundle / name).write_text("x")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        doc = self.root / "doc"
        for package in ("libgtk-4-1", "libglib2.0-0t64"):
            (doc / package).mkdir(parents=True)
            (doc / package / "copyright").write_text(f"license of {package}\n")
        _write_executable(
            self.bin / "ldconfig",
            'printf "\\tlibgtk-4.so.1 (libc6,x86-64) => /usr/lib/libgtk-4.so.1\\n"\n'
            'printf "\\tlibglib-2.0.so.0 (libc6,x86-64) => /usr/lib/libglib-2.0.so.0\\n"\n',
        )
        _write_executable(
            self.bin / "dpkg",
            'case "$2" in\n'
            '  /usr/lib/libgtk-4.so.1) echo "libgtk-4-1:amd64: $2";;\n'
            '  /usr/lib/libglib-2.0.so.0) echo "libglib2.0-0t64:amd64, libglib2.0-data: $2";;\n'
            "  *) exit 1;;\nesac\n",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self):
        script = self.bin / "collect.sh"
        text = (SCRIPTS / "collect_linux_licenses.sh").read_text()
        script.write_text(text.replace("/usr/share/doc/", f"{self.root}/doc/"))
        out = self.root / "out"
        env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}
        result = subprocess.run(
            ["bash", str(script), str(self.bundle.parent), str(out)],
            capture_output=True,
            text=True,
            env=env,
        )
        return result, out

    def test_copies_the_copyright_file_of_each_bundled_system_library(self):
        result, out = self._run()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            sorted(p.name for p in out.iterdir()),
            ["libglib2.0-0t64.copyright", "libgtk-4-1.copyright"],
        )
        self.assertEqual((out / "libgtk-4-1.copyright").read_text(), "license of libgtk-4-1\n")
        self.assertIn("Collected 2 copyright files", result.stdout)

    def test_skips_gracefully_without_dpkg(self):
        script = SCRIPTS / "collect_linux_licenses.sh"
        env = {**os.environ, "PATH": "/nonexistent"}
        result = subprocess.run(
            [BASH, str(script), str(self.bundle.parent), str(self.root / "o")],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("skipping", result.stdout)


@unittest.skipIf(sys.platform == "win32", "needs bash")
class TestMsys2Collector(unittest.TestCase):
    def test_copies_license_folders_of_the_packages_that_own_the_bundled_dlls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prefix = root / "ucrt64"
            (prefix / "bin").mkdir(parents=True)
            for name in ("libgtk-4-1.dll", "zlib1.dll", "unowned.dll"):
                (prefix / "bin" / name).write_text("x")
            (prefix / "share/licenses/gtk4").mkdir(parents=True)
            (prefix / "share/licenses/gtk4/COPYING").write_text("gtk license")
            (prefix / "share/licenses/mingw-w64-ucrt-x86_64-zlib").mkdir(parents=True)
            (prefix / "share/licenses/mingw-w64-ucrt-x86_64-zlib/LICENSE").write_text(
                "zlib license"
            )
            bundle = root / "bundle"
            bundle.mkdir()
            for name in ("libgtk-4-1.dll", "zlib1.dll", "unowned.dll", "notours.dll"):
                (bundle / name).write_text("x")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            _write_executable(
                bin_dir / "pacman",
                'case "$2" in\n'
                '  *libgtk-4-1.dll) echo "$2 is owned by mingw-w64-ucrt-x86_64-gtk4 4.20.0-1";;\n'
                '  *zlib1.dll) echo "$2 is owned by mingw-w64-ucrt-x86_64-zlib 1.3-1";;\n'
                "  *) exit 1;;\nesac\n",
            )
            out = root / "out"
            env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}"}
            result = subprocess.run(
                [
                    "bash",
                    str(SCRIPTS / "collect_msys2_licenses.sh"),
                    str(bundle),
                    str(out),
                    str(prefix),
                ],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((out / "gtk4" / "COPYING").read_text(), "gtk license")
            self.assertEqual((out / "zlib" / "LICENSE").read_text(), "zlib license")
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["gtk4", "zlib"])
            self.assertIn("2 MSYS2 packages", result.stdout)

    def test_skips_gracefully_without_pacman(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    BASH,
                    str(SCRIPTS / "collect_msys2_licenses.sh"),
                    tmp,
                    tmp + "/o",
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "PATH": "/nonexistent"},
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("skipping", result.stdout)


class TestMacosCollector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.brew = self.root / "brew"
        cellar = self.brew / "Cellar"
        (self.brew / "lib").mkdir(parents=True)
        for formula, lib, files in (
            ("gtk4", "libgtk-4.1.dylib", ["COPYING", "README.md"]),
            ("graphene", "libgraphene-1.0.0.dylib", ["LICENSE.txt", "NOTICE"]),
            ("quiet", "libquiet.dylib", []),
        ):
            version_dir = cellar / formula / "1.0"
            (version_dir / "lib").mkdir(parents=True)
            (version_dir / "lib" / lib).write_text("binary")
            for name in files:
                (version_dir / name).write_text(f"{formula} {name}")
            (self.brew / "lib" / lib).symlink_to(version_dir / "lib" / lib)
        self.frameworks = self.root / "Frameworks"
        self.frameworks.mkdir()
        for lib in (
            "libgtk-4.1.dylib",
            "libgraphene-1.0.0.dylib",
            "libquiet.dylib",
            "libpython.dylib",
        ):
            (self.frameworks / lib).write_text("bundled")
        (self.frameworks / "SubDir").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_formula_directory(self):
        path = Path("/opt/homebrew/Cellar/gtk4/4.20.0/lib/libgtk-4.1.dylib")
        self.assertEqual(mu.formula_directory(path), Path("/opt/homebrew/Cellar/gtk4/4.20.0"))
        self.assertIsNone(mu.formula_directory(Path("/usr/lib/libz.dylib")))
        self.assertIsNone(mu.formula_directory(Path("/opt/homebrew/Cellar/gtk4")))

    def test_license_files_of_bundled_formulae_are_copied(self):
        out = self.root / "licenses"
        copied = mu.collect_license_files(self.frameworks, self.brew, out)
        self.assertEqual(copied, ["graphene", "gtk4"])
        self.assertEqual((out / "gtk4" / "COPYING").read_text(), "gtk4 COPYING")
        self.assertFalse((out / "gtk4" / "README.md").exists())
        self.assertEqual(
            sorted(p.name for p in (out / "graphene").iterdir()), ["LICENSE.txt", "NOTICE"]
        )
        self.assertFalse((out / "quiet").exists())  # formula without license files


if __name__ == "__main__":
    unittest.main()
