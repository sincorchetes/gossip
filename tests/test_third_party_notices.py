from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_third_party_notices as gtn  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class FakeMetadata(dict):
    """Minimal stand-in for importlib.metadata.PackageMetadata."""

    def __init__(self, single=None, multi=None):
        super().__init__(single or {})
        self._multi = multi or {}

    def get_all(self, key):
        return self._multi.get(key)


class FakeFile:
    def __init__(self, name):
        self.name = name
        self.suffix = os.path.splitext(name)[1]


class FakeDist:
    def __init__(self, single, multi=None, files=(), directory=None):
        self.metadata = FakeMetadata(single, multi)
        self.files = [FakeFile(n) for n in files]
        self._dir = directory

    def locate_file(self, file):
        return Path(self._dir) / file.name


class TestMetadataParsing(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(gtn.normalize("Typing_Extensions"), "typing-extensions")

    def test_license_label_prefers_the_spdx_expression(self):
        meta = FakeMetadata({"License-Expression": "Apache-2.0 OR BSD-3-Clause", "License": "x"})
        self.assertEqual(gtn.license_label(meta), "Apache-2.0 OR BSD-3-Clause")

    def test_license_label_uses_short_license_field(self):
        self.assertEqual(gtn.license_label(FakeMetadata({"License": "MIT"})), "MIT")

    def test_license_label_ignores_long_or_unknown_text(self):
        self.assertEqual(
            gtn.license_label(FakeMetadata({"License": "UNKNOWN"})), "see license text"
        )
        long_text = FakeMetadata({"License": "line one\nline two"})
        self.assertEqual(gtn.license_label(long_text), "see license text")

    def test_license_label_falls_back_to_classifiers(self):
        meta = FakeMetadata(
            multi={
                "Classifier": ["License :: OSI Approved", "License :: OSI Approved :: BSD License"]
            }
        )
        self.assertEqual(gtn.license_label(meta), "BSD License")

    def test_project_url_prefers_labelled_urls_then_home_page(self):
        meta = FakeMetadata(multi={"Project-URL": ["Issues, http://i", "Source, http://s"]})
        self.assertEqual(gtn.project_url(meta), "http://s")
        self.assertEqual(gtn.project_url(FakeMetadata({"Home-page": "http://h"})), "http://h")
        self.assertEqual(
            gtn.project_url(FakeMetadata(multi={"Project-URL": ["Other, http://o"]})), "http://o"
        )
        self.assertEqual(gtn.project_url(FakeMetadata()), "")


class TestCollectAndRender(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "LICENSE").write_text("MIT text (c) A\n", encoding="utf-8")
        (base / "NOTICE").write_text("Shared notice\n", encoding="utf-8")
        (base / "module.py").write_text("print()", encoding="utf-8")
        self.dists = [
            FakeDist(
                {"Name": "Alpha", "License": "MIT"}, files=["LICENSE", "module.py"], directory=base
            ),
            FakeDist(
                {"Name": "beta_pkg", "License": "MIT"}, files=["LICENSE", "NOTICE"], directory=base
            ),
            FakeDist(
                {"Name": "gamma", "License": "GPL-3.0"}, files=["missing/LICENSE"], directory=base
            ),
            FakeDist({"Name": "pyinstaller", "License": "GPL"}, directory=base),
        ]

    def tearDown(self):
        self.tmp.cleanup()

    def test_collect_skips_build_only_and_reports_missing(self):
        pinned = {
            "alpha": "1.0",
            "beta-pkg": "2.0",
            "gamma": "3.0",
            "pyinstaller": "9",
            "ghost": "1",
        }
        packages, missing = gtn.collect_packages(pinned, self.dists)
        self.assertEqual([p.name for p in packages], ["Alpha", "beta_pkg", "gamma"])
        self.assertEqual(missing, ["ghost"])
        self.assertEqual(packages[0].version, "1.0")
        self.assertEqual([n for n, _ in packages[0].texts], ["LICENSE"])
        self.assertEqual(packages[2].texts, [])  # unreadable file is skipped

    def test_identical_texts_are_printed_once_with_all_their_users(self):
        packages, _ = gtn.collect_packages({"alpha": "1", "beta-pkg": "1"}, self.dists)
        groups = gtn.group_texts(packages)
        shared = [g for g in groups if g[1] == "MIT text (c) A"][0]
        self.assertEqual(shared[2], ["Alpha", "beta_pkg"])
        self.assertEqual(len(groups), 2)

    def test_render_contains_every_section(self):
        packages, _ = gtn.collect_packages({"alpha": "1.0"}, self.dists)
        natives = [
            {
                "name": "GTK 4",
                "license": "LGPL-2.1-or-later",
                "url": "https://gtk.org",
                "note": "A note.",
            },
            {"name": "Pipe|name", "license": "MIT", "url": "https://x"},
        ]
        text = gtn.render(packages, natives, [("LGPL", "LGPL body")])
        for expected in (
            "# Third-party notices",
            "| GTK 4 | LGPL-2.1-or-later | https://gtk.org |",
            "Pipe\\|name",
            "A note.",
            "| Alpha | 1.0 | MIT |",
            "MIT text (c) A",
            "### LGPL",
            "LGPL body",
        ):
            self.assertIn(expected, text)

    def test_locked_packages_reads_pins_from_lock_files(self):
        lock = Path(self.tmp.name) / "lock.txt"
        lock.write_text(
            "# comment\nFoo_Bar==1.2 ; python_version >= '3' \\\n    --hash=sha256:aa\nbaz==3\n",
            encoding="utf-8",
        )
        self.assertEqual(gtn.locked_packages([lock]), {"foo-bar": "1.2", "baz": "3"})


class TestCommittedNotices(unittest.TestCase):
    """The committed THIRD_PARTY_NOTICES.md must mention every package that is shipped."""

    def setUp(self):
        self.text = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")

    def test_every_locked_runtime_package_is_listed(self):
        pinned = gtn.locked_packages(ROOT / name for name in gtn.LOCK_FILES)
        rows = {
            gtn.normalize(line.split("|")[1].strip())
            for line in self.text.splitlines()
            if line.startswith("| ") and line.count("|") >= 5
        }
        missing = sorted(n for n in pinned if n not in gtn.BUILD_ONLY and n not in rows)
        self.assertEqual(missing, [], "Regenerate with scripts/generate_third_party_notices.py")

    def test_main_native_components_and_license_texts_are_present(self):
        for expected in (
            "GTK 4",
            "libadwaita",
            "PyGObject",
            "GNU LESSER GENERAL PUBLIC LICENSE",
            "PYTHON SOFTWARE FOUNDATION LICENSE",
            "Apache License",
        ):
            self.assertIn(expected, self.text)

    def test_every_packaged_license_text_is_a_real_file(self):
        for name in ("LGPL-2.1.txt", "PSF-2.0.txt", "native-components.json"):
            self.assertTrue((ROOT / "packaging" / "licenses" / name).is_file(), name)


class TestMain(unittest.TestCase):
    def test_main_writes_the_file_from_a_given_site_packages(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "notices.md"
            original = gtn.locked_packages
            try:
                gtn.locked_packages = lambda paths: {"nonexistent-pkg-for-test": "1"}
                with self.assertRaises(SystemExit):  # no metadata for the pinned package
                    gtn.main(["x", "--output", str(out), "--site-packages", tmp])
            finally:
                gtn.locked_packages = original


class TestNativeComponentsData(unittest.TestCase):
    def setUp(self):
        import json

        path = ROOT / "packaging" / "licenses" / "native-components.json"
        self.components = json.loads(path.read_text(encoding="utf-8"))["components"]

    def test_every_entry_has_name_license_and_url(self):
        for item in self.components:
            for key in ("name", "license", "url"):
                self.assertTrue(item.get(key), f"{item.get('name')} lacks {key}")

    def test_names_are_unique(self):
        names = [item["name"] for item in self.components]
        self.assertEqual(len(names), len(set(names)))

    def test_gpl_only_bundled_libraries_are_declared(self):
        by_name = {item["name"]: item for item in self.components}
        self.assertEqual(by_name["JBIG-KIT and LZO"]["license"], "GPL-2.0-or-later")
        self.assertIn("GCC-exception", by_name["libstdc++ and libgcc runtime"]["license"])
        self.assertEqual(by_name["Pango"]["license"], "LGPL-2.0-or-later")


if __name__ == "__main__":
    unittest.main()
