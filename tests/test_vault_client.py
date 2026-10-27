from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from src.i18n import set_language
from src.models import SecretVersionItem
from src.providers.vault import VaultClient, discovery, normalize_address, normalize_mount
from src.providers.vault.api import VaultAPIError, VaultHTTP
from src.providers.vault.ops import (
    format_payload,
    parse_payload,
)

ADDR = "https://vault.example.com:8200"


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code: int, errors=None, raw: bytes | None = None) -> urllib.error.HTTPError:
    body = raw if raw is not None else json.dumps({"errors": errors or []}).encode()
    return urllib.error.HTTPError(ADDR, code, "x", {}, io.BytesIO(body))


class TestDiscovery(unittest.TestCase):
    def test_address_rules(self):
        self.assertEqual(normalize_address(f" {ADDR}/ "), ADDR)
        self.assertEqual(normalize_address("http://localhost:8200"), "http://localhost:8200")
        self.assertEqual(normalize_address("http://127.0.0.1:8200/"), "http://127.0.0.1:8200")
        for bad in ("http://vault.example.com", "vault.example.com", "ftp://x", ""):
            with self.assertRaises(ValueError):
                normalize_address(bad)

    def test_mount(self):
        self.assertEqual(normalize_mount(" /kv/ "), "kv")
        self.assertEqual(normalize_mount(None), "secret")
        self.assertEqual(normalize_mount("/"), "secret")

    @patch.dict(
        os.environ, {"BAO_ADDR": "https://bao", "VAULT_NAMESPACE": "team", "BAO_CACERT": "/ca"}
    )
    def test_environment_detection(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("VAULT_ADDR", None)
            os.environ.pop("VAULT_CACERT", None)
            self.assertEqual(discovery.detect_address(), "https://bao")
            self.assertEqual(discovery.detect_namespace(), "team")
            self.assertEqual(discovery.detect_cafile(), "/ca")

    def test_token_sources(self):
        with patch.dict(os.environ, {"VAULT_TOKEN": "env-token"}):
            self.assertEqual(discovery.detect_token(), "env-token")
        with patch.dict(os.environ, {}, clear=True):
            with patch("os.path.expanduser", return_value="/nonexistent-home"):
                self.assertIsNone(discovery.detect_token())
            opened = MagicMock()
            opened.__enter__.return_value.read.return_value = " file-token\n"
            with patch("builtins.open", return_value=opened):
                self.assertEqual(discovery.detect_token(), "file-token")
            empty = MagicMock()
            empty.__enter__.return_value.read.return_value = "  "
            with patch("builtins.open", return_value=empty):
                self.assertIsNone(discovery.detect_token())


class TestHTTP(unittest.TestCase):
    def make(self, **kwargs):
        return VaultHTTP(ADDR, "tok", **kwargs)

    @patch("urllib.request.urlopen")
    def test_request_builds_url_and_headers(self, urlopen):
        urlopen.return_value = FakeResponse(b'{"ok": 1}')
        out = self.make(namespace="ns").request(
            "POST", "secret/data/a b/c", body={"x": 1}, query={"version": "2"}
        )
        self.assertEqual(out, {"ok": 1})
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, f"{ADDR}/v1/secret/data/a%20b/c?version=2")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.get_header("X-vault-token"), "tok")
        self.assertEqual(req.get_header("X-vault-namespace"), "ns")
        self.assertEqual(json.loads(req.data), {"x": 1})

    @patch("urllib.request.urlopen")
    def test_empty_body(self, urlopen):
        urlopen.return_value = FakeResponse(b"")
        self.assertIsNone(self.make().request("DELETE", "secret/metadata/a"))

    @patch("urllib.request.urlopen")
    def test_http_errors(self, urlopen):
        urlopen.side_effect = http_error(403, ["permission denied"])
        with self.assertRaises(VaultAPIError) as ctx:
            self.make().request("GET", "x")
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(ctx.exception.errors, ["permission denied"])

        urlopen.side_effect = http_error(500, raw=b"<html>")
        with self.assertRaises(VaultAPIError) as ctx:
            self.make().request("GET", "x")
        self.assertEqual(ctx.exception.errors, [])
        self.assertIn("500", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_connection_failure(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("connection refused")
        with self.assertRaises(VaultAPIError) as ctx:
            self.make().request("GET", "x")
        self.assertEqual(ctx.exception.status, 0)
        self.assertIn("connection refused", str(ctx.exception))

    def test_cafile_builds_context(self):
        with patch("ssl.create_default_context") as create:
            self.make(cafile="/ca.pem")
            create.assert_called_once_with(cafile="/ca.pem")


class TestPayloadHelpers(unittest.TestCase):
    def test_parse_and_format(self):
        self.assertEqual(parse_payload('{"user": "a", "n": 1}'), {"user": "a", "n": 1})
        for text in ("plain", "{}", "[1]", "42", ""):
            self.assertEqual(parse_payload(text), {"value": text})
        self.assertEqual(format_payload({"value": "plain"}), "plain")
        self.assertEqual(json.loads(format_payload({"user": "a", "n": 1})), {"user": "a", "n": 1})
        self.assertEqual(json.loads(format_payload({"value": 5})), {"value": 5})


class TestVaultClient(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        self.client = VaultClient(address=ADDR, mount="kv")
        self.http = MagicMock()
        self.client._http_client = self.http

    def reply(self, *responses):
        self.http.request.side_effect = list(responses)

    def test_properties(self):
        c = self.client
        self.assertEqual(c.provider_id, "vault")
        self.assertEqual(c.display_name, "HashiCorp Vault / OpenBao")
        self.assertTrue(c.supports_version_toggling)
        self.assertTrue(c.supports_version_destroy)
        self.assertIn("kv", c.context_subtitle)
        for text in (
            c.icon_name,
            c.context_btn_tooltip,
            c.loading_message,
            c.empty_message,
            c.error_message,
        ):
            self.assertTrue(text)
        with patch.dict(os.environ, {}, clear=True):
            self.assertIn("no server", VaultClient().context_subtitle)

    def test_list_secrets_walks_folders(self):
        def fake(method, path, **kwargs):
            tree = {
                "kv/metadata/": ["root", "app/", "Zeta"],
                "kv/metadata/app/": ["db", "deep/"],
                "kv/metadata/app/deep/": ["key"],
            }
            return {"data": {"keys": tree[path]}}

        self.http.request.side_effect = fake
        names = [s.secret_id for s in self.client.list_secrets()]
        self.assertEqual(names, ["app/db", "app/deep/key", "root", "Zeta"])
        self.assertEqual(self.client.list_secrets()[0].provider, "vault")

    def test_list_secrets_empty_mount_and_depth_limit(self):
        self.reply(VaultAPIError(404, []))
        self.assertEqual(self.client.list_secrets(), [])

        def endless(method, path, **kwargs):
            return {"data": {"keys": ["f/"]}}

        self.http.request.side_effect = endless
        self.assertEqual(self.client.list_secrets(), [])
        self.assertLessEqual(self.http.request.call_count, 9 + 2)

    def test_list_versions(self):
        self.reply(
            {
                "data": {
                    "versions": {
                        "1": {
                            "created_time": "2026-01-01T00:00:00Z",
                            "deletion_time": "2026-01-02T00:00:00Z",
                            "destroyed": False,
                        },
                        "2": {"created_time": "2026-01-03T00:00:00Z", "deletion_time": ""},
                        "3": {"created_time": "2026-01-04T00:00:00Z", "destroyed": True},
                    }
                }
            }
        )
        versions = self.client.list_versions("app/db")
        self.assertEqual([v.version_id for v in versions], ["3", "2", "1"])
        self.assertEqual([v.state for v in versions], ["DESTROYED", "ENABLED", "DISABLED"])
        self.assertEqual(versions[1].name, "app/db@2")

    def test_access_payload(self):
        self.reply({"data": {"data": {"value": "s3cret"}}})
        self.assertEqual(self.client.access_secret_payload("app/db"), ("s3cret", False))
        self.assertEqual(self.http.request.call_args.kwargs["query"], None)

        self.reply({"data": {"data": {"user": "a"}}})
        text, binary = self.client.access_secret_payload("app/db@2")
        self.assertEqual(json.loads(text), {"user": "a"})
        self.assertEqual(self.http.request.call_args.kwargs["query"], {"version": "2"})
        self.assertEqual(self.http.request.call_args.args[1], "kv/data/app/db")

    def test_access_payload_errors(self):
        self.reply(VaultAPIError(404, []))
        with self.assertRaises(FileNotFoundError):
            self.client.access_secret_payload("app/db")
        self.reply({"data": {"data": None}})
        with self.assertRaises(FileNotFoundError):
            self.client.access_secret_payload("app/db@1")
        self.reply(VaultAPIError(403, ["permission denied"]))
        with self.assertRaises(PermissionError):
            self.client.access_secret_payload("app/db")
        self.reply(VaultAPIError(401, []))
        with self.assertRaises(PermissionError):
            self.client.access_secret_payload("app/db")
        self.reply(VaultAPIError(0, ["refused"]))
        with self.assertRaisesRegex(RuntimeError, "refused"):
            self.client.access_secret_payload("app/db")
        self.reply(VaultAPIError(500, ["boom"]))
        with self.assertRaisesRegex(RuntimeError, "boom"):
            self.client.access_secret_payload("app/db")

    def test_create_secret(self):
        self.reply({"data": {"version": 1, "created_time": "2026-01-01T00:00:00Z"}}, None)
        item = self.client.create_secret("app/new", "hello", labels={"env": "prod"})
        first = self.http.request.call_args_list[0]
        self.assertEqual(first.kwargs["body"], {"data": {"value": "hello"}, "options": {"cas": 0}})
        self.assertEqual(
            self.http.request.call_args_list[1].kwargs["body"],
            {"custom_metadata": {"env": "prod"}},
        )
        self.assertEqual(
            (item.secret_id, item.provider, item.labels), ("app/new", "vault", {"env": "prod"})
        )

    def test_create_secret_without_labels_and_conflict(self):
        self.reply({"data": {"version": 1}})
        self.client.create_secret("a", "x")
        self.assertEqual(self.http.request.call_count, 1)

        self.reply(
            VaultAPIError(400, ["check-and-set parameter did not match the current version"])
        )
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.client.create_secret("a", "x")
        self.reply(VaultAPIError(400, ["other"]))
        with self.assertRaisesRegex(RuntimeError, "other"):
            self.client.create_secret("a", "x")

    def test_add_version_delete_and_version_actions(self):
        self.reply({"data": {"version": 4, "created_time": "2026-01-01T00:00:00Z"}})
        version = self.client.add_secret_version("app/db@2", '{"k": "v"}')
        self.assertEqual((version.version_id, version.name), ("4", "app/db@4"))
        self.assertEqual(self.http.request.call_args.kwargs["body"], {"data": {"k": "v"}})

        self.reply(None)
        self.client.delete_secret("app/db")
        self.assertEqual(self.http.request.call_args.args[:2], ("DELETE", "kv/metadata/app/db"))

        item = SecretVersionItem(version_id="3", name="app/db@3")
        self.reply(None)
        self.client.toggle_version_state(item, enable=False)
        self.assertEqual(self.http.request.call_args.args[:2], ("POST", "kv/delete/app/db"))
        self.assertEqual(self.http.request.call_args.kwargs["body"], {"versions": [3]})
        self.reply(None)
        self.client.toggle_version_state("app/db@3", enable=True)
        self.assertEqual(self.http.request.call_args.args[1], "kv/undelete/app/db")
        self.reply(None)
        self.client.destroy_version(item)
        self.assertEqual(self.http.request.call_args.args[1], "kv/destroy/app/db")
        with self.assertRaises(ValueError):
            self.client.destroy_version("app/db")


class TestConnection(unittest.TestCase):
    def test_http_requires_address_and_token(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError):
                VaultClient()._http()
            with patch("src.providers.vault.client.detect_token", return_value=None):
                with self.assertRaises(PermissionError):
                    VaultClient(address=ADDR)._http()

    def test_http_is_built_once_with_typed_token(self):
        client = VaultClient(address=ADDR, namespace="ns")
        client.configure(f"{ADDR}/", " /kv/ ", " team ", "typed")
        self.assertEqual((client.address, client.mount, client.namespace), (ADDR, "kv", "team"))
        with patch.dict(os.environ, {}, clear=True):
            http = client._http()
            self.assertIs(client._http(), http)
        self.assertEqual(http._token, "typed")
        self.assertEqual(http._namespace, "team")

    def test_configure_rejects_plain_http(self):
        with self.assertRaises(ValueError):
            VaultClient().configure("http://vault.example.com", None, None, "t")

    def test_lock_forgets_typed_token(self):
        client = VaultClient(address=ADDR)
        client.configure(ADDR, None, None, "typed")
        client._http()
        client.lock()
        self.assertIsNone(client._typed_token)
        self.assertIsNone(client._http_client)
        with patch.dict(os.environ, {}, clear=True):
            with patch("src.providers.vault.client.detect_token", return_value=None):
                with self.assertRaises(PermissionError):
                    client._http()

    def test_open_context_dialog(self):
        callback = MagicMock()
        with patch("src.ui.dialogs.show_change_vault_dialog") as show:
            VaultClient().open_context_dialog("window", callback)
        show.assert_called_once()
        self.assertEqual(show.call_args.args[0], "window")


if __name__ == "__main__":
    unittest.main()
