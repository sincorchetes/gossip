from __future__ import annotations

import json
import os
import stat
import sys
import unittest
from unittest.mock import MagicMock, patch

from src import state
from src.providers import (
    AnsibleVaultClient,
    AWSSecretClient,
    AzureSecretClient,
    BaseSecretProvider,
    GCPSecretClient,
    KubernetesClient,
    SSMClient,
    VaultClient,
)
from tests.window_case import WindowCase


class TestStateFile(unittest.TestCase):
    def test_path_per_platform(self):
        with patch.dict(os.environ, {"GOSSIP_STATE_FILE": ""}):
            with (
                patch.object(sys, "platform", "linux"),
                patch.dict(os.environ, {"XDG_CONFIG_HOME": "/xdg"}),
            ):
                self.assertEqual(state.state_path(), os.path.join("/xdg", "gossip", "state.json"))
            with patch.object(sys, "platform", "linux"), patch.dict(os.environ, {}, clear=True):
                self.assertIn(os.path.join(".config", "gossip"), state.state_path())
            with patch.object(sys, "platform", "darwin"):
                self.assertIn("Application Support", state.state_path())
            with (
                patch.object(sys, "platform", "win32"),
                patch.dict(os.environ, {"APPDATA": "C:/Users/me/AppData"}),
            ):
                self.assertIn("AppData", state.state_path())
            with patch.object(sys, "platform", "win32"), patch.dict(os.environ, {}, clear=True):
                self.assertIn("gossip", state.state_path())

    def test_round_trip_with_private_permissions(self):
        state.save("aws", {"aws": {"profile": "dev", "region": "eu-west-1"}, "gcp": {}})
        loaded = state.load()
        self.assertEqual(loaded["provider"], "aws")
        self.assertEqual(loaded["contexts"]["aws"], {"profile": "dev", "region": "eu-west-1"})
        if sys.platform != "win32":
            mode = stat.S_IMODE(os.stat(state.state_path()).st_mode)
            self.assertEqual(mode, 0o600)

    def test_credentials_are_never_written(self):
        state.save(
            "vault",
            {
                "vault": {
                    "address": "https://v",
                    "token": "t",
                    "Password": "p",
                    "api_key": "k",
                    "client_secret": "s",
                    "n": 5,
                    "empty": "",
                }
            },
        )
        with open(state.state_path(), encoding="utf-8") as handle:
            raw = handle.read()
        self.assertEqual(state.load()["contexts"]["vault"], {"address": "https://v"})
        for leaked in ('"t"', '"p"', '"k"', '"s"'):
            self.assertNotIn(leaked, raw)

    def test_missing_or_damaged_files(self):
        empty = {"provider": None, "contexts": {}, "recents": {}, "ui": {}}
        self.assertEqual(state.load(), empty)
        for content in ("{not json", "[1, 2]"):
            with open(state.state_path(), "w", encoding="utf-8") as handle:
                handle.write(content)
            self.assertEqual(state.load(), empty)
        with open(state.state_path(), "w", encoding="utf-8") as handle:
            json.dump({"provider": 5, "contexts": ["x"]}, handle)
        self.assertEqual(state.load(), empty)
        with open(state.state_path(), "w", encoding="utf-8") as handle:
            json.dump(
                {"provider": "gcp", "contexts": {"gcp": "oops", "aws": {"region": "r"}}}, handle
            )
        loaded = state.load()
        self.assertEqual(loaded["contexts"], {"gcp": {}, "aws": {"region": "r"}})

    def test_save_failures_are_swallowed(self):
        with patch("os.makedirs", side_effect=OSError("read-only")):
            state.save("gcp", {})
        with patch("os.replace", side_effect=OSError("busy")):
            state.save("gcp", {})
        self.assertEqual(state.load()["provider"], None)
        self.assertEqual(
            [f for f in os.listdir(os.path.dirname(state.state_path())) if f.startswith(".state-")],
            [],
        )


class TestProviderContexts(unittest.TestCase):
    def test_base_defaults(self):
        self.assertEqual(BaseSecretProvider.saved_context(MagicMock()), {})
        self.assertIsNone(BaseSecretProvider.restore_context(MagicMock(), {"x": "y"}))

    def test_gcp(self):
        client = GCPSecretClient(project_id="p1")
        self.assertEqual(client.saved_context(), {"project": "p1"})
        other = GCPSecretClient()
        self.assertEqual(other.saved_context(), {})
        other.restore_context({})
        self.assertIsNone(other._project_id)
        other.restore_context({"project": "p2"})
        self.assertEqual(other.project_id, "p2")

    def test_aws_and_ssm(self):
        for cls in (AWSSecretClient, SSMClient):
            client = cls(profile_name="dev", region_name="eu-west-1")
            self.assertEqual(client.saved_context(), {"profile": "dev", "region": "eu-west-1"})
            fresh = cls()
            self.assertEqual(fresh.saved_context(), {})
            fresh.restore_context({})
            fresh.restore_context({"profile": "prod", "region": "us-east-2"})
            self.assertEqual((fresh.profile_name, fresh.region_name), ("prod", "us-east-2"))
            part = cls(profile_name="a")
            part.restore_context({"region": "ap-south-1"})
            self.assertEqual((part.profile_name, part.region_name), ("a", "ap-south-1"))

    def test_azure(self):
        client = AzureSecretClient(vault_name="kv")
        self.assertEqual(client.saved_context(), {"vault": "kv"})
        fresh = AzureSecretClient()
        self.assertEqual(fresh.saved_context(), {})
        fresh.restore_context({})
        fresh.restore_context({"vault": "other"})
        self.assertEqual(fresh.vault_name, "other")

    def test_ansible_saves_the_path_but_never_a_password(self):
        with patch.dict(os.environ, {}, clear=False):
            client = AnsibleVaultClient(vault_file="/tmp/v.yml", password="hunter2")
        saved = client.saved_context()
        self.assertEqual(saved, {"vault_file": "/tmp/v.yml"})
        self.assertNotIn("hunter2", json.dumps(saved))
        client._vault_file = None
        self.assertEqual(client.saved_context(), {})
        client.restore_context({"vault_file": "/does/not/exist.yml"})
        self.assertIsNone(client._vault_file)
        client.restore_context({})
        here = os.path.abspath(__file__)
        client.restore_context({"vault_file": here})
        self.assertEqual(client.vault_file, here)

    def test_vault_never_saves_the_token(self):
        client = VaultClient(address="https://v:8200", mount="kv", namespace="ns")
        client.configure("https://v:8200", "kv", "ns", "tok")
        saved = client.saved_context()
        self.assertEqual(saved, {"address": "https://v:8200", "mount": "kv", "namespace": "ns"})
        fresh = VaultClient()
        fresh.restore_context(saved)
        self.assertEqual(
            (fresh.address, fresh.mount, fresh.namespace), ("https://v:8200", "kv", "ns")
        )
        self.assertIsNone(fresh._typed_token)
        fresh.restore_context({"address": "http://evil.example.com", "mount": "x"})
        self.assertEqual((fresh.address, fresh.mount), ("https://v:8200", "kv"))
        fresh.restore_context({})
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(VaultClient().saved_context(), {"mount": "secret"})

    def test_kubernetes(self):
        client = KubernetesClient(context="dev", namespace="apps")
        self.assertEqual(client.saved_context(), {"context": "dev", "namespace": "apps"})
        fresh = KubernetesClient()
        self.assertEqual(fresh.saved_context(), {})
        fresh.restore_context({"context": "prod"})
        self.assertEqual(fresh.saved_context(), {"context": "prod"})
        fresh.restore_context({"namespace": "x"})
        self.assertEqual(fresh.saved_context(), {"context": "prod", "namespace": "x"})


class TestWindowRemembers(WindowCase):
    def test_changing_provider_saves_it_without_touching_contexts(self):
        state.save("gcp", {"gcp": {"project": "kept"}})
        self.window.active_provider = self.mock_aws
        self.window._remember()
        loaded = state.load()
        self.assertEqual(loaded["provider"], "aws")
        self.assertEqual(loaded["contexts"], {"gcp": {"project": "kept"}})

    def test_confirmed_context_is_saved(self):
        self.mock_gcp.saved_context.return_value = {"project": "new-proj"}
        self.window.active_provider = self.mock_gcp
        with patch.object(self.window, "_load_secrets_async"):
            self.mock_gcp.open_context_dialog.side_effect = lambda win, done: done()
            self.window._on_change_context_clicked(None)
        self.assertEqual(state.load()["contexts"]["gcp"], {"project": "new-proj"})

    def test_switching_provider_in_the_dropdown_remembers_it(self):
        keys = list(self.window.providers)
        with patch.object(self.window, "_load_secrets_async"):
            self.window.provider_dropdown.set_selected(keys.index("aws"))
        self.assertEqual(state.load()["provider"], "aws")


class TestStartup(unittest.TestCase):
    def make_app(self, **kwargs):
        from src.ui.app import GossipApplication

        return GossipApplication(**kwargs)

    def test_saved_contexts_fill_in_what_the_command_line_left_out(self):
        state.save(
            "gcp",
            {
                "gcp": {"project": "saved-proj"},
                "aws": {"profile": "saved", "region": "sa-east-1"},
                "ssm": {"region": "ap-south-1"},
                "k8s": {"context": "saved-ctx"},
                "vault": {"address": "https://saved:8200"},
                "azure": {"vault": "saved-kv"},
            },
        )
        app = self.make_app()
        self.assertEqual(app.gcp_client.project_id, "saved-proj")
        self.assertEqual(app.aws_client.profile_name, "saved")
        self.assertEqual(app.ssm_client.region_name, "ap-south-1")
        self.assertEqual(app.k8s_client.context, "saved-ctx")
        self.assertEqual(app.vault_client.address, "https://saved:8200")
        self.assertEqual(app.azure_client.vault_name, "saved-kv")

    def test_command_line_wins_over_saved_state(self):
        state.save("gcp", {"gcp": {"project": "saved"}, "k8s": {"context": "saved"}})
        app = self.make_app(project_id="cli-proj", kube_context="cli-ctx")
        self.assertEqual(app.gcp_client.project_id, "cli-proj")
        self.assertEqual(app.k8s_client.context, "cli-ctx")


class TestWindowRecordsRecents(WindowCase):
    def test_changing_a_context_records_it(self):
        self.mock_gcp.saved_context.return_value = {"project": "new"}
        self.window.active_provider = self.mock_gcp
        self.window._remember(context_changed=True)
        self.assertEqual(state.load()["recents"]["gcp"], [{"project": "new"}])
        self.window._remember()  # switching provider does not add to the history
        self.assertEqual(state.load()["recents"]["gcp"], [{"project": "new"}])


class TestRecents(unittest.TestCase):
    def test_the_newest_context_goes_first_without_duplicates_and_the_list_is_capped(self):
        recents = {}
        for i in range(8):
            recents = state.remember_recent(recents, "gcp", {"project": f"p{i}"})
        recents = state.remember_recent(recents, "gcp", {"project": "p5"})
        projects = [c["project"] for c in recents["gcp"]]
        self.assertEqual(projects, ["p5", "p7", "p6", "p4", "p3"])

    def test_empty_contexts_and_credentials_are_not_remembered(self):
        self.assertEqual(state.remember_recent({}, "vault", {}), {})
        recents = state.remember_recent({}, "vault", {"address": "https://v", "token": "t"})
        self.assertEqual(recents, {"vault": [{"address": "https://v"}]})

    def test_recents_round_trip_and_survive_saving_the_rest(self):
        recents = {"aws": [{"profile": "dev"}, {"profile": "prod", "region": "eu-west-1"}]}
        state.save("aws", {"aws": {"profile": "dev"}}, recents)
        self.assertEqual(state.load()["recents"], recents)
        state.save("gcp", {})  # omitted: keep the saved ones
        self.assertEqual(state.load()["recents"], recents)
        state.save("gcp", {}, {})  # explicit empty: clear
        self.assertEqual(state.load()["recents"], {})

    def test_damaged_recents_are_ignored(self):
        with open(state.state_path(), "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "provider": "gcp",
                    "recents": {"gcp": "oops", "aws": [{"token": "t"}, 5, {"a": "b"}], "x": 3},
                },
                handle,
            )
        self.assertEqual(state.load()["recents"], {"aws": [{"a": "b"}]})
        with open(state.state_path(), "w", encoding="utf-8") as handle:
            json.dump({"recents": []}, handle)
        self.assertEqual(state.load()["recents"], {})


if __name__ == "__main__":
    unittest.main()
