from __future__ import annotations

import argparse
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from src import registry
from src.main import _build_parser
from src.providers import BaseSecretProvider
from tests.window_case import WindowCase

EXPECTED_ORDER = ["gcp", "aws", "azure", "ansible", "vault", "ssm", "k8s"]


class TestRegistry(unittest.TestCase):
    def test_ids_and_order(self):
        self.assertEqual(list(registry.PROVIDER_IDS), EXPECTED_ORDER)

    def test_every_option_is_unique_and_documented(self):
        flags = [o.flag for o in registry.all_options()]
        names = registry.option_names()
        self.assertEqual(len(flags), len(set(flags)))
        self.assertEqual(len(names), len(set(names)))
        for option in registry.all_options():
            self.assertTrue(option.help())
            self.assertTrue(option.flag.startswith("--"))

    def test_every_provider_argument_refers_to_a_known_option(self):
        known = set(registry.option_names())
        for spec in registry.PROVIDERS:
            self.assertTrue(set(spec.arguments.values()) <= known, spec.id)

    def test_the_parser_gets_every_option_from_the_registry(self):
        parser = _build_parser()
        args = parser.parse_args(
            [
                "-p",
                "proj",
                "--aws-profile",
                "dev",
                "--vault-addr",
                "https://v",
                "--kube-context",
                "c",
            ]
        )
        self.assertEqual(
            (args.project_id, args.aws_profile, args.vault_addr, args.kube_context),
            ("proj", "dev", "https://v", "c"),
        )
        self.assertIsNone(args.azure_vault)
        self.assertIsInstance(parser, argparse.ArgumentParser)
        with self.assertRaises(SystemExit):
            parser.parse_args(["-P", "nope"])

    def test_creating_a_client_passes_only_its_own_options(self):
        values = {"aws_profile": "prod", "aws_region": "eu-west-1", "project_id": "ignored"}
        aws = registry.PROVIDERS[1].create(values)
        ssm = registry.PROVIDERS[5].create(values)
        for client in (aws, ssm):
            self.assertEqual((client.profile_name, client.region_name), ("prod", "eu-west-1"))
        self.assertEqual(registry.PROVIDERS[0].create({"project_id": "p"}).project_id, "p")

    def test_explicit_means_the_user_chose_something_for_that_provider(self):
        gcp, aws, ssm = registry.PROVIDERS[0], registry.PROVIDERS[1], registry.PROVIDERS[5]
        self.assertFalse(gcp.is_explicit({}))
        self.assertFalse(gcp.is_explicit({"project_id": None, "aws_profile": "x"}))
        self.assertTrue(gcp.is_explicit({"project_id": "p"}))
        self.assertTrue(aws.is_explicit({"aws_region": "r"}))
        self.assertTrue(ssm.is_explicit({"aws_region": "r"}))  # shares the AWS options

    def test_create_clients_builds_all_and_honours_overrides(self):
        ready = MagicMock(spec=BaseSecretProvider)
        clients = registry.create_clients({}, {"vault": ready})
        self.assertEqual(list(clients), EXPECTED_ORDER)
        self.assertIs(clients["vault"], ready)
        self.assertTrue(all(isinstance(c, BaseSecretProvider) for c in clients.values()))

    def test_importing_the_registry_does_not_load_the_cloud_sdks(self):
        code = (
            "import sys; from src import registry; "
            "heavy = [m for m in ('boto3', 'azure.keyvault.secrets', 'google.cloud') if m in sys.modules]; "
            "print(heavy)"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        self.assertEqual(out.stdout.strip(), "[]")


class TestFrozenBuildsSeeEveryClient(unittest.TestCase):
    def test_the_application_imports_every_client_statically(self):
        """The registry loads clients by name, so the app must import them for PyInstaller."""
        code = (
            "import sys; import src.ui.app; "
            "from src import registry; "
            "missing = [s.client for s in registry.PROVIDERS if s.client.split(':')[0] not in sys.modules]; "
            "print(missing)"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        self.assertEqual(out.stdout.strip(), "[]")


class TestApplicationAndWindow(WindowCase):
    def test_unknown_options_are_rejected(self):
        from src.ui.app import GossipApplication

        with self.assertRaisesRegex(TypeError, "unknown provider option"):
            GossipApplication(not_an_option="x")

    def test_the_application_exposes_clients_by_id_and_the_old_attribute_names(self):
        from src.ui.app import GossipApplication

        app = GossipApplication(kube_context="ctx", vault_addr="https://v:8200")
        self.assertEqual(list(app.clients), EXPECTED_ORDER)
        self.assertIs(app.k8s_client, app.clients["k8s"])
        self.assertEqual(app.k8s_client.context, "ctx")
        self.assertEqual(app.vault_client.address, "https://v:8200")

    def test_the_window_accepts_a_providers_dict_or_the_id_client_shorthand(self):
        from src.ui.windows.main import MainWindow

        gcp, aws = MagicMock(spec=BaseSecretProvider), MagicMock(spec=BaseSecretProvider)
        for mock, pid in ((gcp, "gcp"), (aws, "aws")):
            mock.provider_id = pid
            mock.display_name = pid
            mock.icon_name = "dialog-password-symbolic"
            mock.context_subtitle = pid
            mock.context_btn_tooltip = pid
            mock.loading_message = mock.empty_message = mock.error_message = pid
            mock.supports_version_toggling = mock.supports_version_destroy = False
            mock.list_secrets.return_value = []
        with patch("gi.repository.GLib.idle_add"):
            window = MainWindow(providers={"gcp": gcp}, aws_client=aws)
        self.assertIs(window.providers["gcp"], gcp)
        self.assertIs(window.providers["aws"], aws)
        self.assertEqual(list(window.providers), EXPECTED_ORDER)


if __name__ == "__main__":
    unittest.main()
