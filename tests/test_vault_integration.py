"""Run the Vault / OpenBao provider against a real server.

Skipped unless GOSSIP_TEST_VAULT_ADDR and GOSSIP_TEST_VAULT_TOKEN are set. CI starts a throwaway
`bao server -dev` and sets them. To run it locally:

    bao server -dev -dev-root-token-id=devroot &
    GOSSIP_TEST_VAULT_ADDR=http://127.0.0.1:8200 GOSSIP_TEST_VAULT_TOKEN=devroot \
        pytest tests/test_vault_integration.py
"""

from __future__ import annotations

import json
import os
import unittest
import uuid

from src.exceptions import (
    PermissionDeniedError,
    ResourceNotFoundError,
    SecretConflictError,
)
from src.providers.vault import VaultClient
from src.transfer import (
    build_export_document,
    collect_export_entries,
    import_entries,
    parse_import_text,
)

ADDR = os.environ.get("GOSSIP_TEST_VAULT_ADDR", "")
TOKEN = os.environ.get("GOSSIP_TEST_VAULT_TOKEN", "")


def connect(token: str = TOKEN) -> VaultClient:
    client = VaultClient()
    client.configure(ADDR, "secret", None, token)
    return client


class TestIntegrationIsConfigured(unittest.TestCase):
    """CI sets GOSSIP_REQUIRE_VAULT_TESTS so a lost variable fails instead of skipping silently."""

    def test_server_is_reachable_when_required(self):
        if not os.environ.get("GOSSIP_REQUIRE_VAULT_TESTS"):
            self.skipTest("integration tests are optional here")
        self.assertTrue(ADDR and TOKEN, "GOSSIP_TEST_VAULT_ADDR / TOKEN did not reach pytest")


@unittest.skipUnless(ADDR and TOKEN, "needs a running Vault / OpenBao dev server")
class TestAgainstRealServer(unittest.TestCase):
    def setUp(self):
        self.client = connect()
        self.prefix = f"gossip-it-{uuid.uuid4().hex[:8]}"
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for secret in self.client.list_secrets():
            if secret.secret_id.startswith(self.prefix):
                self.client.delete_secret(secret.secret_id)

    def name(self, suffix: str) -> str:
        return f"{self.prefix}/{suffix}"

    def test_create_read_and_list_nested_paths(self):
        self.client.create_secret(self.name("app/db"), '{"user": "admin", "password": "p4ss"}')
        self.client.create_secret(self.name("plain"), "just text")
        ids = [s.secret_id for s in self.client.list_secrets()]
        self.assertIn(self.name("app/db"), ids)
        self.assertIn(self.name("plain"), ids)
        text, binary = self.client.access_secret_payload(self.name("app/db"))
        self.assertEqual(json.loads(text), {"user": "admin", "password": "p4ss"})
        self.assertFalse(binary)
        self.assertEqual(self.client.access_secret_payload(self.name("plain"))[0], "just text")

    def test_creating_never_overwrites(self):
        self.client.create_secret(self.name("once"), "first")
        with self.assertRaises(SecretConflictError):
            self.client.create_secret(self.name("once"), "second")
        self.assertEqual(self.client.access_secret_payload(self.name("once"))[0], "first")

    def test_version_lifecycle(self):
        name = self.name("versions")
        self.client.create_secret(name, "v1")
        self.client.add_secret_version(name, "v2")
        versions = self.client.list_versions(name)
        self.assertEqual([v.version_id for v in versions], ["2", "1"])
        self.assertEqual([v.state for v in versions], ["ENABLED", "ENABLED"])
        self.assertEqual(self.client.access_secret_payload(f"{name}@1")[0], "v1")

        self.client.toggle_version_state(f"{name}@1", enable=False)
        self.assertEqual(self.client.list_versions(name)[1].state, "DISABLED")
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload(f"{name}@1")

        self.client.toggle_version_state(f"{name}@1", enable=True)
        self.assertEqual(self.client.access_secret_payload(f"{name}@1")[0], "v1")

        self.client.destroy_version(f"{name}@1")
        self.assertEqual(self.client.list_versions(name)[1].state, "DESTROYED")
        self.assertEqual(self.client.access_secret_payload(name)[0], "v2")

    def test_delete_removes_every_version(self):
        name = self.name("gone")
        self.client.create_secret(name, "x")
        self.client.add_secret_version(name, "y")
        self.client.delete_secret(name)
        self.assertNotIn(name, [s.secret_id for s in self.client.list_secrets()])
        with self.assertRaises(ResourceNotFoundError):
            self.client.access_secret_payload(name)

    def test_text_that_looks_like_json_stays_text(self):
        name = self.name("jsonish")
        self.client.create_secret(name, json.dumps({"value": '{"a": "1"}'}))
        shown = self.client.access_secret_payload(name)[0]
        self.client.add_secret_version(name, shown)
        self.assertEqual(self.client.access_secret_payload(name)[0], shown)

    def test_export_and_import_round_trip(self):
        source = {
            self.name("rt/multi"): '{"user": "admin", "password": "p4ss"}',
            self.name("rt/plain"): "contraseña ñ ✓",
        }
        for name, value in source.items():
            self.client.create_secret(name, value)
        secrets = [s for s in self.client.list_secrets() if s.secret_id in source]
        entries, problems = collect_export_entries(self.client, secrets, include_values=True)
        self.assertEqual(problems, [])
        document = build_export_document("vault", entries, True)
        self.client.delete_secret(self.name("rt/multi"))
        self.client.delete_secret(self.name("rt/plain"))

        imported = parse_import_text(json.dumps(document))
        result = import_entries(self.client, imported, set())
        self.assertEqual(result.failed, [])
        self.assertEqual(sorted(result.created), sorted(source))
        for name, value in source.items():
            self.assertEqual(
                json.loads(self.client.access_secret_payload(name)[0])
                if value.startswith("{")
                else self.client.access_secret_payload(name)[0],
                json.loads(value) if value.startswith("{") else value,
            )

    def test_bad_token_is_a_permission_error(self):
        with self.assertRaises(PermissionDeniedError):
            connect("not-a-valid-token").list_secrets()

    def test_unreachable_server_reports_a_clear_error(self):
        client = VaultClient()
        client.configure("http://127.0.0.1:9", "secret", None, TOKEN)
        with self.assertRaisesRegex(Exception, "Vault"):
            client.list_secrets()


if __name__ == "__main__":
    unittest.main()
