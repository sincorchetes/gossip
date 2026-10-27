from __future__ import annotations

import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_flatpak_sources as gen  # noqa: E402
from pip_lock_subset import parse_lock  # noqa: E402

APP_ID = "com.github.sincorchetes.gossip_gcp"
FLATPAK = ROOT / "packaging" / "flatpak"


class TestWheelChoice(unittest.TestCase):
    def test_pure_python_wheels_serve_every_architecture(self):
        for name in ("idna-3.10-py3-none-any.whl", "six-1.16.0-py2.py3-none-any.whl"):
            self.assertEqual(gen.wheel_arch(name, "314"), "any", name)

    def test_native_wheels_must_match_the_interpreter_and_the_glibc_family(self):
        arch = gen.wheel_arch
        self.assertEqual(
            arch("cffi-2.1-cp314-cp314-manylinux2014_x86_64.manylinux_2_17_x86_64.whl", "314"),
            "x86_64",
        )
        self.assertEqual(arch("cffi-2.1-cp314-cp314-manylinux_2_17_aarch64.whl", "314"), "aarch64")
        self.assertEqual(
            arch("cryptography-50-cp311-abi3-manylinux_2_28_x86_64.whl", "314"), "x86_64"
        )
        self.assertIsNone(
            arch("cffi-2.1-cp313-cp313-manylinux_2_17_x86_64.whl", "314")
        )  # other Python
        self.assertIsNone(arch("x-1-cp314-cp314-musllinux_1_2_x86_64.whl", "314"))  # not glibc
        self.assertIsNone(arch("x-1-cp314-cp314-macosx_11_0_arm64.whl", "314"))
        self.assertIsNone(arch("x-1-cp314-cp314-win_amd64.whl", "314"))
        self.assertIsNone(
            arch("x-1-cp314-cp314-manylinux_2_99_x86_64.whl", "314")
        )  # newer glibc than the runtime
        self.assertIsNone(arch("not-a-wheel.tar.gz", "314"))
        self.assertIsNone(
            arch("x-1-cp315-abi3-manylinux_2_28_x86_64.whl", "314")
        )  # needs a newer Python

    def test_pick_files_prefers_wheels_and_ignores_sdists_and_yanked_files(self):
        files = [
            {"filename": "p-1.tar.gz", "packagetype": "sdist"},
            {"filename": "p-1-py3-none-any.whl", "packagetype": "bdist_wheel", "yanked": True},
            {"filename": "p-1-cp314-cp314-manylinux_2_28_x86_64.whl", "packagetype": "bdist_wheel"},
        ]
        self.assertEqual(list(gen.pick_files(files, "314")), ["x86_64"])


class TestBuildModule(unittest.TestCase):
    LOCK = (
        "pure==1.0 \\\n    --hash=sha256:"
        + "a" * 64
        + "\nnative==2.0 \\\n    --hash=sha256:"
        + "b" * 64
        + " \\\n    --hash=sha256:"
        + "c" * 64
        + "\npyinstaller==6 \\\n    --hash=sha256:"
        + "d" * 64
        + "\nmacholib==1 ; sys_platform == 'darwin' \\\n    --hash=sha256:"
        + "e" * 64
        + "\n"
    )

    def files(self, name, version):
        if name == "pure":
            return [
                {
                    "filename": "pure-1.0-py3-none-any.whl",
                    "packagetype": "bdist_wheel",
                    "url": "https://files.pythonhosted.org/pure.whl",
                    "digests": {"sha256": "a" * 64},
                }
            ]
        return [
            {
                "filename": "native-2.0-cp314-cp314-manylinux_2_28_x86_64.whl",
                "packagetype": "bdist_wheel",
                "url": "https://files.pythonhosted.org/n-x.whl",
                "digests": {"sha256": "b" * 64},
            },
            {
                "filename": "native-2.0-cp314-cp314-manylinux_2_28_aarch64.whl",
                "packagetype": "bdist_wheel",
                "url": "https://files.pythonhosted.org/n-a.whl",
                "digests": {"sha256": "c" * 64},
            },
        ]

    def test_module_has_one_source_per_needed_file_and_skips_build_tools_and_other_platforms(self):
        module = gen.build_module(self.LOCK, "314", fetch=self.files)
        urls = {s["url"].rsplit("/", 1)[1]: s.get("only-arches") for s in module["sources"]}
        self.assertEqual(urls, {"pure.whl": None, "n-x.whl": ["x86_64"], "n-a.whl": ["aarch64"]})
        self.assertIn("--no-index", module["build-commands"][0])
        self.assertIn("--no-deps", module["build-commands"][0])

    def test_files_that_are_not_in_the_lock_are_refused(self):
        def tampered(name, version):
            return [{**f, "digests": {"sha256": "f" * 64}} for f in self.files(name, version)]

        with self.assertRaises(SystemExit) as ctx:
            gen.build_module(self.LOCK, "314", fetch=tampered)
        self.assertIn("not in the lock", str(ctx.exception))

    def test_a_missing_architecture_is_reported(self):
        def only_x86(name, version):
            return [f for f in self.files(name, version) if "aarch64" not in f["filename"]]

        with self.assertRaises(SystemExit) as ctx:
            gen.build_module(self.LOCK, "314", fetch=only_x86)
        self.assertIn("aarch64", str(ctx.exception))

    def test_requirement_parsing(self):
        self.assertEqual(
            gen.parse_requirement("Foo_Bar==1.2.3 ; python_version >= '3'"), ("foo-bar", "1.2.3")
        )
        with self.assertRaises(ValueError):
            gen.parse_requirement("foo>=1")


class TestCommittedFiles(unittest.TestCase):
    """The generated sources must stay in step with the lock the other packages use."""

    def setUp(self):
        self.module = json.loads((FLATPAK / "python3-deps.json").read_text(encoding="utf-8"))
        self.lock = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")

    def test_every_source_is_a_hash_from_the_lock_on_pypi(self):
        hashes = set(re.findall(r"sha256:([0-9a-f]{64})", self.lock))
        for source in self.module["sources"]:
            self.assertIn(source["sha256"], hashes, source["url"])
            self.assertTrue(
                source["url"].startswith("https://files.pythonhosted.org/"), source["url"]
            )
            self.assertTrue(source["url"].endswith(".whl"))

    def test_every_runtime_package_of_the_lock_is_present(self):
        wanted = {
            name
            for name, lines in parse_lock(self.lock)
            if name not in gen.SKIPPED and gen._applies_to_linux(lines[0])
        }
        present = {
            gen.normalize(s["url"].rsplit("/", 1)[1].split("-")[0]) for s in self.module["sources"]
        }
        self.assertEqual(wanted - present, set())
        for needed in ("boto3", "ansible-core", "cryptography", "pyyaml", "grpcio", "google-auth"):
            self.assertIn(needed, present)

    def test_native_wheels_exist_for_both_architectures(self):
        per_arch = {"x86_64": set(), "aarch64": set()}
        for source in self.module["sources"]:
            for arch in source.get("only-arches", per_arch):
                per_arch[arch].add(source["url"].rsplit("/", 1)[1].split("-")[0])
        self.assertEqual(
            per_arch["x86_64"], per_arch["aarch64"] | set()
        )  # same package set per arch

    def test_build_tools_are_not_shipped(self):
        names = " ".join(s["url"] for s in self.module["sources"]).lower()
        for tool in ("pyinstaller", "altgraph", "macholib", "pefile"):
            self.assertNotIn(tool, names)


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.manifest = yaml.safe_load((FLATPAK / f"{APP_ID}.yml").read_text(encoding="utf-8"))

    def test_identity_and_runtime(self):
        self.assertEqual(self.manifest["app-id"], APP_ID)
        self.assertEqual(self.manifest["runtime"], "org.gnome.Platform")
        self.assertEqual(self.manifest["sdk"], "org.gnome.Sdk")
        self.assertEqual(self.manifest["command"], "gossip")
        self.assertIn("python3-deps.json", self.manifest["modules"])

    def test_permissions_are_narrow(self):
        args = self.manifest["finish-args"]
        for broad in (
            "--filesystem=host",
            "--filesystem=home",
            "--filesystem=/",
            "--device=all",
            "--socket=ssh-auth",
        ):
            self.assertNotIn(broad, args)
        for needed in ("--share=network", "--socket=wayland", "--socket=fallback-x11"):
            self.assertIn(needed, args)
        for path in ("~/.aws", "~/.azure", "~/.config/gcloud", "~/.kube", "~/.vault-token"):
            self.assertIn(f"--filesystem={path}:ro", args)  # credentials are read-only
        self.assertIn("--system-talk-name=org.freedesktop.login1", args)  # lock on suspend

    def test_the_app_module_installs_what_the_desktop_needs(self):
        app = next(m for m in self.manifest["modules"] if isinstance(m, dict))
        commands = "\n".join(app["build-commands"])
        for fragment in ("src locales", "/app/bin/gossip", ".desktop", ".metainfo.xml", ".svg"):
            self.assertIn(fragment, commands)
        skip = app["sources"][0]["skip"]
        for heavy in (".git", ".devenv", "tests"):
            self.assertIn(heavy, skip)

    def test_launcher_runs_the_application_from_the_install_prefix(self):
        script = (FLATPAK / "gossip.sh").read_text(encoding="utf-8")
        self.assertIn("/app/lib/gossip", script)
        self.assertIn("src.main", script)
        self.assertTrue(script.startswith("#!/bin/sh"))


class TestDesktopIntegration(unittest.TestCase):
    def test_metainfo_matches_the_application(self):
        root = ET.parse(ROOT / "data" / f"{APP_ID}.metainfo.xml").getroot()
        self.assertEqual(root.findtext("id"), APP_ID)
        self.assertEqual(root.findtext("project_license"), "GPL-3.0-or-later")
        self.assertEqual(root.find("launchable").text, f"{APP_ID}.desktop")
        self.assertIsNotNone(root.find("releases/release"))

    def test_desktop_entry_names_the_same_application(self):
        text = (ROOT / "data" / f"{APP_ID}.desktop").read_text(encoding="utf-8")
        self.assertIn(f"Icon={APP_ID}", text)
        self.assertIn(f"StartupWMClass={APP_ID}", text)
        self.assertTrue(
            (ROOT / "data" / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg").exists()
        )

    def test_release_workflow_builds_and_publishes_the_bundles(self):
        workflow = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        )
        self.assertIn("build-flatpak", workflow["jobs"])
        self.assertIn("build-flatpak", workflow["jobs"]["publish-release"]["needs"])
        arches = [
            m["arch"] for m in workflow["jobs"]["build-flatpak"]["strategy"]["matrix"]["include"]
        ]
        self.assertEqual(arches, ["x86_64", "aarch64"])

    def test_the_bundle_points_at_flathub_for_its_runtime(self):
        """Without this, a system that lacks Flathub cannot find the runtime to install."""
        text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("--runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo", text)

    def test_the_dependency_refresh_regenerates_the_sources(self):
        text = (ROOT / ".github" / "workflows" / "update-build-deps.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("generate_flatpak_sources.py", text)


if __name__ == "__main__":
    unittest.main()
