from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import macho_utils as mu  # noqa: E402

MACHO_64_LE = b"\xcf\xfa\xed\xfe" + b"\0" * 60

OTOOL_L = """/tmp/libfoo.dylib:
\t/usr/local/opt/openssl@3/lib/libssl.3.dylib (compatibility version 3.0.0, current version 3.0.0)
\t@rpath/libglib-2.0.0.dylib (compatibility version 8801.0.0, current version 8801.2.0)
\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1351.0.0)
"""

OTOOL_RPATH = """Load command 12
          cmd LC_RPATH
      cmdsize 32
         path @loader_path/../Frameworks (offset 12)
Load command 13
          cmd LC_RPATH
      cmdsize 40
         path /opt/homebrew/lib (offset 12)
"""


class TestMachoDetection(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_is_macho_by_magic_number(self):
        binary = self.root / "lib.dylib"
        binary.write_bytes(MACHO_64_LE)
        text = self.root / "notes.txt"
        text.write_text("hello")
        self.assertTrue(mu.is_macho(binary))
        self.assertFalse(mu.is_macho(text))
        self.assertFalse(mu.is_macho(self.root / "missing"))

    def test_symlinks_are_not_macho(self):
        binary = self.root / "real.dylib"
        binary.write_bytes(MACHO_64_LE)
        link = self.root / "link.dylib"
        link.symlink_to(binary)
        self.assertFalse(mu.is_macho(link))

    def test_unreadable_file_is_not_macho(self):
        binary = self.root / "lib.dylib"
        binary.write_bytes(MACHO_64_LE)
        with patch("builtins.open", side_effect=OSError("denied")):
            self.assertFalse(mu.is_macho(binary))

    def test_system_library_detection(self):
        self.assertTrue(mu.is_system_lib("/usr/lib/libSystem.B.dylib"))
        self.assertTrue(mu.is_system_lib("/System/Library/Frameworks/AppKit.framework/AppKit"))
        self.assertFalse(mu.is_system_lib("/usr/local/opt/openssl@3/lib/libssl.3.dylib"))
        self.assertFalse(mu.is_system_lib("@rpath/libglib-2.0.0.dylib"))


class TestOtoolParsing(unittest.TestCase):
    def test_dependencies_skip_header_and_versions(self):
        with patch("subprocess.check_output", return_value=OTOOL_L):
            deps = mu.get_dependencies(Path("/tmp/libfoo.dylib"))
        self.assertEqual(
            deps,
            [
                "/usr/local/opt/openssl@3/lib/libssl.3.dylib",
                "@rpath/libglib-2.0.0.dylib",
                "/usr/lib/libSystem.B.dylib",
            ],
        )

    def test_dependencies_empty_when_otool_fails(self):
        with patch("subprocess.check_output", side_effect=OSError("no otool")):
            self.assertEqual(mu.get_dependencies(Path("x")), [])

    def test_rpaths_are_extracted(self):
        with patch("subprocess.check_output", return_value=OTOOL_RPATH):
            self.assertEqual(
                mu.get_rpaths(Path("x")),
                ["@loader_path/../Frameworks", "/opt/homebrew/lib"],
            )

    def test_rpaths_empty_when_otool_fails(self):
        with patch("subprocess.check_output", side_effect=OSError("no otool")):
            self.assertEqual(mu.get_rpaths(Path("x")), [])


class TestLibraryCopying(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        self.dst = self.root / "dst"
        self.src.mkdir()
        self.dst.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_copies_real_file_and_recreates_versioned_symlink(self):
        real = self.src / "libfoo.1.2.3.dylib"
        real.write_bytes(b"data")
        link = self.src / "libfoo.1.dylib"
        link.symlink_to(real.name)

        copied = mu.copy_lib_with_symlinks(link, self.dst)

        self.assertEqual([p.name for p in copied], ["libfoo.1.2.3.dylib"])
        self.assertEqual((self.dst / "libfoo.1.2.3.dylib").read_bytes(), b"data")
        self.assertTrue((self.dst / "libfoo.1.dylib").is_symlink())

    def test_missing_source_copies_nothing(self):
        self.assertEqual(mu.copy_lib_with_symlinks(self.src / "nope.dylib", self.dst), [])

    def test_existing_destination_is_not_overwritten(self):
        real = self.src / "libbar.dylib"
        real.write_bytes(b"new")
        (self.dst / "libbar.dylib").write_bytes(b"old")
        self.assertEqual(mu.copy_lib_with_symlinks(real, self.dst), [])
        self.assertEqual((self.dst / "libbar.dylib").read_bytes(), b"old")

    def test_symlink_creation_failure_falls_back_to_copy(self):
        real = self.src / "libbaz.2.dylib"
        real.write_bytes(b"data")
        link = self.src / "libbaz.dylib"
        link.symlink_to(real.name)
        with patch.object(Path, "symlink_to", side_effect=OSError("no symlinks")):
            copied = mu.copy_lib_with_symlinks(link, self.dst)
        self.assertEqual(sorted(p.name for p in copied), ["libbaz.2.dylib", "libbaz.dylib"])
        self.assertFalse((self.dst / "libbaz.dylib").is_symlink())


class TestSeeding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.brew = Path(self.tmp.name) / "brew"
        self.frameworks = Path(self.tmp.name) / "Frameworks"
        self.frameworks.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_homebrew_seed_copies_only_essential_libraries(self):
        lib = self.brew / "lib"
        lib.mkdir(parents=True)
        (lib / "libgtk-4.1.dylib").write_bytes(b"gtk")
        (lib / "libunrelated.dylib").write_bytes(b"x")
        mu.seed_homebrew_libraries(self.brew, self.frameworks)
        names = {p.name for p in self.frameworks.iterdir()}
        self.assertIn("libgtk-4.1.dylib", names)
        self.assertNotIn("libunrelated.dylib", names)

    def test_homebrew_seed_without_lib_dir_is_noop(self):
        self.assertEqual(mu.seed_homebrew_libraries(self.brew, self.frameworks), [])

    def test_openssl_replaces_stale_copy_collected_by_pyinstaller(self):
        ssl_lib = self.brew / "opt" / "openssl@3" / "lib"
        ssl_lib.mkdir(parents=True)
        (ssl_lib / "libssl.3.dylib").write_bytes(b"new-ssl")
        (ssl_lib / "libcrypto.3.dylib").write_bytes(b"new-crypto")
        (self.frameworks / "libssl.3.dylib").write_bytes(b"OLD-ssl")

        mu.seed_openssl(self.brew, self.frameworks)

        self.assertEqual((self.frameworks / "libssl.3.dylib").read_bytes(), b"new-ssl")
        self.assertEqual((self.frameworks / "libcrypto.3.dylib").read_bytes(), b"new-crypto")

    def test_openssl_without_homebrew_package_is_noop(self):
        (self.frameworks / "libssl.3.dylib").write_bytes(b"keep")
        self.assertEqual(mu.seed_openssl(self.brew, self.frameworks), [])
        self.assertEqual((self.frameworks / "libssl.3.dylib").read_bytes(), b"keep")


class TestDependencyResolution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.brew = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_absolute_existing_path_wins(self):
        lib = self.brew / "libabs.dylib"
        lib.write_bytes(b"x")
        self.assertEqual(mu.resolve_dependency_source(str(lib), self.brew), lib.resolve())

    def test_found_in_brew_lib(self):
        (self.brew / "lib").mkdir()
        lib = self.brew / "lib" / "libfoo.dylib"
        lib.write_bytes(b"x")
        self.assertEqual(
            mu.resolve_dependency_source("@rpath/libfoo.dylib", self.brew), lib.resolve()
        )

    def test_found_in_opt_package(self):
        pkg = self.brew / "opt" / "openssl@3" / "lib"
        pkg.mkdir(parents=True)
        lib = pkg / "libssl.3.dylib"
        lib.write_bytes(b"x")
        self.assertEqual(mu.resolve_dependency_source("libssl.3.dylib", self.brew), lib.resolve())

    def test_unknown_dependency_returns_none(self):
        (self.brew / "opt").mkdir()
        self.assertIsNone(mu.resolve_dependency_source("libnope.dylib", self.brew))


if __name__ == "__main__":
    unittest.main()


class TestBundleVersionAndIcon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = Path(self.tmp.name) / "gossip.app"
        (self.app / "Contents" / "Resources").mkdir(parents=True)
        (self.app / "Contents" / "MacOS").mkdir()
        import plistlib

        with (self.app / "Contents" / "Info.plist").open("wb") as fh:
            plistlib.dump(
                {"CFBundleShortVersionString": "0.0.0", "CFBundleIconFile": "gossip.icns"}, fh
            )

    def test_the_release_version_is_written_and_the_rest_kept(self):
        import plistlib

        mu.stamp_bundle_version(self.app, "v0.3.69")
        with (self.app / "Contents" / "Info.plist").open("rb") as fh:
            info = plistlib.load(fh)
        self.assertEqual(info["CFBundleShortVersionString"], "0.3.69")
        self.assertEqual(info["CFBundleVersion"], "0.3.69")
        self.assertEqual(info["CFBundleIconFile"], "gossip.icns")

    def test_the_source_version_is_read_from_the_package(self):
        import bundle_macos

        root = Path(self.tmp.name)
        (root / "src").mkdir()
        (root / "src" / "__init__.py").write_text('__version__ = "1.2.3"\n')
        self.assertEqual(bundle_macos.read_source_version(root), "1.2.3")
        (root / "src" / "__init__.py").write_text("# nothing\n")
        self.assertEqual(bundle_macos.read_source_version(root), "")

    def test_the_dock_icon_is_found_in_the_bundle_resources(self):
        from src import dock_icon

        icon = self.app / "Contents" / "Resources" / "gossip.icns"
        icon.write_bytes(b"icns")
        with patch.object(sys, "executable", str(self.app / "Contents" / "MacOS" / "gossip")):
            self.assertEqual(dock_icon.find_icns(), os.path.normpath(str(icon)))
        icon.unlink()
        with patch.object(sys, "executable", str(self.app / "Contents" / "MacOS" / "gossip")):
            self.assertIsNone(dock_icon.find_icns())

    def test_setting_the_dock_icon_is_a_no_op_off_macos(self):
        from src import dock_icon

        with patch.object(sys, "platform", "linux"):
            self.assertFalse(dock_icon.set_dock_icon())
