"""Export from one provider and import into another must not change what a secret holds."""

from __future__ import annotations

import base64
import json
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock

from src.providers.kubernetes import KubernetesClient
from src.providers.kubernetes.api import KubeAPIError
from src.providers.vault import VaultClient
from src.providers.vault.api import VaultAPIError
from src.transfer import (
    build_export_document,
    collect_export_entries,
    import_entries,
    parse_import_text,
)

CASES = {
    "plain": "just text",
    "multi": '{"user": "admin", "password": "p4ss"}',
    "json-looking-text": None,  # filled below: a single key whose value is JSON text
    "unicode": "contraseña ñ ✓",
}


class FakeVault:
    """In-memory KV v2 backend behind VaultClient._http."""

    def __init__(self):
        self.data: Dict[str, Dict[str, Any]] = {}

    def request(self, method, path, body=None, query=None):
        parts = path.split("/", 2)
        kind, name = parts[1], parts[2] if len(parts) > 2 else ""
        if kind == "metadata" and method == "GET" and query:
            if name == "":
                return {"data": {"keys": sorted(self.data)}}
            raise VaultAPIError(404, [])
        if kind == "metadata" and method == "GET":
            return {"data": {"versions": {"1": {"created_time": "2026-01-01T00:00:00Z"}}}}
        if kind == "data" and method == "GET":
            if name not in self.data:
                raise VaultAPIError(404, [])
            return {"data": {"data": self.data[name]}}
        if kind == "data" and method == "POST":
            if (body.get("options") or {}).get("cas") == 0 and name in self.data:
                raise VaultAPIError(400, ["check-and-set parameter did not match"])
            self.data[name] = body["data"]
            return {"data": {"version": 1}}
        raise AssertionError(f"unexpected {method} {path}")


class FakeKube:
    """In-memory Secrets API behind KubernetesClient._http."""

    def __init__(self):
        self.secrets: Dict[str, Dict[str, Any]] = {}

    def request(self, method, path, body=None, query=None):
        name = path.rsplit("/", 1)[1] if not path.endswith("/secrets") else ""
        if method == "GET" and not name:
            return {"items": list(self.secrets.values()), "metadata": {}}
        if method == "GET":
            if name not in self.secrets:
                raise KubeAPIError(404, "not found")
            return self.secrets[name]
        if method == "POST":
            n = body["metadata"]["name"]
            if n in self.secrets:
                raise KubeAPIError(409, f'secrets "{n}" already exists')
            self.secrets[n] = {**body, "metadata": {**body["metadata"], "resourceVersion": "1"}}
            return self.secrets[n]
        raise AssertionError(f"unexpected {method} {path}")


def make_vault() -> VaultClient:
    client = VaultClient(address="https://v", mount="secret")
    client._http_client = FakeVault()
    return client


def make_kube() -> KubernetesClient:
    client = KubernetesClient(context="c", namespace="ns")
    client._http_client = FakeKube()
    return client


class RoundTrip(unittest.TestCase):
    def values(self):
        cases = dict(CASES)
        cases["json-looking-text"] = json.dumps({"value": '{"a": "1"}'})
        return cases

    def check(self, make):
        source, target = make(), make()
        for name, text in self.values().items():
            source.create_secret(name, text)
        secrets = source.list_secrets()
        entries, problems = collect_export_entries(source, secrets, include_values=True)
        self.assertEqual(problems, [])
        document = build_export_document(source.provider_id, entries, True)
        imported = parse_import_text(json.dumps(document))
        result = import_entries(target, imported, set())
        self.assertEqual(result.failed, [])
        self.assertEqual(sorted(result.created), sorted(self.values()))
        for name in self.values():
            self.assertEqual(
                target.access_secret_payload(name)[0],
                source.access_secret_payload(name)[0],
                name,
            )

    def test_vault(self):
        self.check(make_vault)

    def test_kubernetes(self):
        self.check(make_kube)

    def test_from_vault_to_kubernetes(self):
        source, target = make_vault(), make_kube()
        source.create_secret("multi", '{"user": "admin", "password": "p4ss"}')
        entries, _ = collect_export_entries(source, source.list_secrets(), True)
        import_entries(target, entries, set())
        stored = target._http_client.secrets["multi"]["data"]
        self.assertEqual(
            {k: base64.b64decode(v).decode() for k, v in stored.items()},
            {"user": "admin", "password": "p4ss"},
        )

    def test_text_that_looks_like_json_is_not_restructured(self):
        for make in (make_vault, make_kube):
            client = make()
            client.create_secret("t", json.dumps({"value": '{"a": "1"}'}))
            shown = client.access_secret_payload("t")[0]
            if isinstance(client, VaultClient):
                client.add_secret_version("t", shown)
            else:
                client._http_client.request = MagicMock(
                    side_effect=[client._http_client.secrets["t"], {"metadata": {}}]
                )
                client.add_secret_version("t", shown)
                stored = client._http_client.request.call_args.kwargs["body"]["data"]
                self.assertEqual(list(stored), ["value"])
                continue
            self.assertEqual(client._http_client.data["t"], {"value": '{"a": "1"}'})


if __name__ == "__main__":
    unittest.main()
