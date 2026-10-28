from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

import yaml

from src.i18n import set_language
from src.providers.kubernetes import KubernetesClient, kubeconfig
from src.providers.kubernetes.api import KubeAPIError, KubeHTTP, build_ssl_context
from src.providers.kubernetes.kubeconfig import ClusterAccess
from src.providers.kubernetes.ops import (
    decode_data,
    encode_data,
    format_payload,
    parse_payload,
    strip_version,
)


def b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


def kube_doc(**user):
    return {
        "current-context": "dev",
        "clusters": [
            {
                "name": "c1",
                "cluster": {
                    "server": "https://k8s.example.com:6443/",
                    "certificate-authority-data": b64("PEM"),
                },
            }
        ],
        "users": [{"name": "u1", "user": user or {"token": "tok"}}],
        "contexts": [
            {"name": "dev", "context": {"cluster": "c1", "user": "u1", "namespace": "apps"}}
        ],
    }


class KubeconfigCase(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name: str, doc) -> str:
        path = os.path.join(self.dir.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(doc, handle) if not isinstance(doc, str) else handle.write(doc)
        return path

    def env(self, *paths: str):
        return patch.dict(os.environ, {"KUBECONFIG": os.pathsep.join(paths)})


class TestKubeconfig(KubeconfigCase):
    def test_paths(self):
        with patch.dict(os.environ, {"KUBECONFIG": ""}):
            self.assertTrue(
                kubeconfig.kubeconfig_paths()[0].endswith(os.path.join(".kube", "config"))
            )
        with self.env("/a", "/b"):
            self.assertEqual(kubeconfig.kubeconfig_paths(), ["/a", "/b"])

    def test_merge_first_wins_and_bad_files_are_skipped(self):
        first = self.write("a", kube_doc())
        other = kube_doc()
        other["current-context"] = "prod"
        other["contexts"].append({"name": "prod", "context": {"cluster": "c1", "user": "u1"}})
        other["users"][0]["user"]["token"] = "other"
        second = self.write("b", other)
        broken = self.write("c", "a: [")
        notdict = self.write("d", "- 1\n- 2\n")
        with self.env(first, second, broken, notdict, "/nonexistent"):
            self.assertEqual(kubeconfig.list_contexts(), ["dev", "prod"])
            self.assertEqual(kubeconfig.current_context(), "dev")
            self.assertEqual(kubeconfig.resolve_context("prod").token, "tok")
            self.assertEqual(kubeconfig.context_namespace("prod"), "default")
            self.assertEqual(kubeconfig.context_namespace("dev"), "apps")

    def test_current_context_fallbacks(self):
        doc = kube_doc()
        del doc["current-context"]
        with self.env(self.write("a", doc)):
            self.assertEqual(kubeconfig.current_context(), "dev")
        doc["contexts"].append({"name": "x", "context": {}})
        with self.env(self.write("b", doc)):
            self.assertIsNone(kubeconfig.current_context())

    def test_resolve_token_and_ca(self):
        with self.env(self.write("a", kube_doc())):
            access = kubeconfig.resolve_context(None)
        self.assertEqual(
            (access.server, access.token, access.ca_pem, access.namespace),
            ("https://k8s.example.com:6443", "tok", "PEM", "apps"),
        )

    def test_resolve_files(self):
        ca = os.path.join(self.dir.name, "ca.pem")
        tokfile = os.path.join(self.dir.name, "token")
        cert = os.path.join(self.dir.name, "cert.pem")
        key = os.path.join(self.dir.name, "key.pem")
        for path, text in (
            (ca, "CAFILE\n"),
            (tokfile, "filetoken\n"),
            (cert, "CERT"),
            (key, "KEY"),
        ):
            with open(path, "w") as handle:
                handle.write(text)
        doc = kube_doc(**{"tokenFile": tokfile, "client-certificate": cert, "client-key": key})
        doc["clusters"][0]["cluster"] = {"server": "https://s", "certificate-authority": ca}
        with self.env(self.write("a", doc)):
            access = kubeconfig.resolve_context("dev")
        self.assertEqual(
            (access.ca_pem, access.token, access.cert_pem, access.key_pem),
            ("CAFILE", "filetoken", "CERT", "KEY"),
        )

    def test_resolve_inline_client_cert(self):
        doc = kube_doc(**{"client-certificate-data": b64("C"), "client-key-data": b64("K")})
        with self.env(self.write("a", doc)):
            access = kubeconfig.resolve_context("dev")
        self.assertEqual((access.cert_pem, access.key_pem), ("C", "K"))

    def test_resolve_rejections(self):
        with self.env(self.write("none", {})):
            with self.assertRaisesRegex(ValueError, "No Kubernetes context"):
                kubeconfig.resolve_context(None)
        doc = kube_doc()
        doc["clusters"][0]["cluster"] = {}
        with self.env(self.write("a", doc)):
            with self.assertRaisesRegex(ValueError, "server"):
                kubeconfig.resolve_context("dev")
        doc = kube_doc()
        doc["clusters"][0]["cluster"]["insecure-skip-tls-verify"] = True
        with self.env(self.write("b", doc)):
            with self.assertRaisesRegex(ValueError, "TLS verification"):
                kubeconfig.resolve_context("dev")
        for user in ({"auth-provider": {"name": "gcp"}}, {"username": "u", "password": "p"}):
            with self.env(self.write("c", kube_doc(**user))):
                with self.assertRaisesRegex(ValueError, "legacy"):
                    kubeconfig.resolve_context("dev")


class TestExecPlugin(KubeconfigCase):
    def resolve(self, spec):
        with self.env(self.write("a", kube_doc(exec=spec))):
            return kubeconfig.resolve_context("dev")

    def run_result(self, stdout="", returncode=0, stderr=""):
        return subprocess.CompletedProcess([], returncode, stdout, stderr)

    def test_token_and_certs_from_plugin(self):
        out = json.dumps(
            {"status": {"token": "exec-token", "clientCertificateData": "C", "clientKeyData": "K"}}
        )
        spec = {"command": "plugin", "args": ["get"], "env": [{"name": "X", "value": "1"}]}
        with patch("subprocess.run", return_value=self.run_result(out)) as run:
            access = self.resolve(spec)
        self.assertEqual((access.token, access.cert_pem, access.key_pem), ("exec-token", "C", "K"))
        self.assertEqual(run.call_args.args[0], ["plugin", "get"])
        self.assertEqual(run.call_args.kwargs["env"]["X"], "1")

    def test_plugin_failures(self):
        spec = {"command": "plugin"}
        with patch("subprocess.run", side_effect=OSError("missing")):
            with self.assertRaisesRegex(RuntimeError, "could not run"):
                self.resolve(spec)
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("plugin", 30)):
            with self.assertRaisesRegex(RuntimeError, "could not run"):
                self.resolve(spec)
        with patch("subprocess.run", return_value=self.run_result(returncode=1, stderr="denied")):
            with self.assertRaisesRegex(RuntimeError, "denied"):
                self.resolve(spec)
        with patch("subprocess.run", return_value=self.run_result("not json")):
            with self.assertRaisesRegex(RuntimeError, "invalid output"):
                self.resolve(spec)
        with patch("subprocess.run", return_value=self.run_result("{}")):
            self.assertIsNone(self.resolve(spec).token)


class FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestHTTP(unittest.TestCase):
    def make(self, **kwargs):
        with patch("src.providers.kubernetes.api.build_ssl_context"):
            return KubeHTTP(ClusterAccess(server="https://k8s", **kwargs))

    @patch("urllib.request.urlopen")
    def test_request(self, urlopen):
        urlopen.return_value = FakeResponse(b'{"a": 1}')
        out = self.make(token="t").request(
            "POST", "/api/v1/x y", body={"k": 1}, query={"limit": "5"}
        )
        self.assertEqual(out, {"a": 1})
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://k8s/api/v1/x%20y?limit=5")
        self.assertEqual(req.get_header("Authorization"), "Bearer t")
        self.assertEqual(json.loads(req.data), {"k": 1})
        urlopen.return_value = FakeResponse(b"")
        self.assertEqual(self.make().request("GET", "/x"), {})
        self.assertIsNone(urlopen.call_args.args[0].get_header("Authorization"))

    @patch("urllib.request.urlopen")
    def test_errors(self, urlopen):
        body = json.dumps({"message": "forbidden!"}).encode()
        urlopen.side_effect = urllib.error.HTTPError("u", 403, "x", {}, io.BytesIO(body))
        with self.assertRaises(KubeAPIError) as ctx:
            self.make().request("GET", "/x")
        self.assertEqual((ctx.exception.status, ctx.exception.message), (403, "forbidden!"))
        urlopen.side_effect = urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(b"<html>"))
        with self.assertRaises(KubeAPIError) as ctx:
            self.make().request("GET", "/x")
        self.assertEqual(ctx.exception.message, "")
        self.assertIn("500", str(ctx.exception))
        urlopen.side_effect = urllib.error.URLError("refused")
        with self.assertRaises(KubeAPIError) as ctx:
            self.make().request("GET", "/x")
        self.assertEqual(ctx.exception.status, 0)

    def test_ssl_context(self):
        with patch("ssl.create_default_context") as create:
            build_ssl_context(ClusterAccess(server="s"))
            create.assert_called_with()
            build_ssl_context(ClusterAccess(server="s", ca_pem="PEM"))
            create.assert_called_with(cadata="PEM")
            context = create.return_value
            build_ssl_context(ClusterAccess(server="s", cert_pem="C", key_pem="K"))
            cert_path, key_path = context.load_cert_chain.call_args.args
            self.assertTrue(cert_path.endswith("cert.pem") and key_path.endswith("key.pem"))
            self.assertFalse(os.path.exists(cert_path))
            context.load_cert_chain.reset_mock()
            build_ssl_context(ClusterAccess(server="s", cert_pem="C"))
            context.load_cert_chain.assert_not_called()


class TestPayloadHelpers(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")

    def test_decode_encode_round_trip(self):
        raw = {
            "a": b64("plain"),
            "bin": base64.b64encode(b"\xff\xfe").decode(),
            "t": b64("base64:x"),
        }
        decoded = decode_data(raw)
        self.assertEqual(decoded["a"], "plain")
        self.assertEqual(decoded["bin"], "base64:" + raw["bin"])
        self.assertEqual(decoded["t"], "base64:" + raw["t"])
        self.assertEqual(encode_data(decoded), raw)
        with self.assertRaises(ValueError):
            encode_data({"k": "base64:***"})

    def test_parse_and_format(self):
        self.assertEqual(parse_payload('{"a": "1", "b": "2"}'), {"a": "1", "b": "2"})
        for text in ("plain", "{}", "[1]", "5"):
            self.assertEqual(parse_payload(text), {"value": text})
        with self.assertRaisesRegex(ValueError, "strings"):
            parse_payload('{"a": 1}')
        self.assertEqual(format_payload({"value": "x"}), "x")
        self.assertEqual(json.loads(format_payload({"a": "1", "b": "2"})), {"a": "1", "b": "2"})
        self.assertEqual(strip_version("db@123"), "db")
        self.assertEqual(strip_version("db"), "db")


def secret(name="db", data=None, rv="42", **extra):
    return {
        "metadata": {
            "name": name,
            "resourceVersion": rv,
            "creationTimestamp": "2026-01-01T10:00:00Z",
            "labels": {"app": "x"},
        },
        "type": "Opaque",
        "data": data if data is not None else {"value": b64("s3")},
        **extra,
    }


class TestClient(unittest.TestCase):
    def setUp(self):
        set_language("en")
        self.addCleanup(set_language, "es")
        self.client = KubernetesClient(context="dev", namespace="apps")
        self.http = MagicMock()
        self.client._http_client = self.http

    def reply(self, *responses):
        self.http.request.side_effect = list(responses)

    def test_properties(self):
        c = self.client
        self.assertEqual((c.provider_id, c.display_name), ("k8s", "Kubernetes Secrets"))
        self.assertIn("apps", c.context_subtitle)
        for text in (
            c.icon_name,
            c.context_btn_tooltip,
            c.loading_message,
            c.empty_message,
            c.error_message,
        ):
            self.assertTrue(text)
        self.assertFalse(c.supports_version_toggling)
        with patch("src.providers.kubernetes.client.current_context", return_value=None):
            self.assertIn("no context", KubernetesClient().context_subtitle)

    def test_namespace_defaults_to_the_context_one(self):
        with patch("src.providers.kubernetes.client.context_namespace", return_value="team"):
            self.assertEqual(KubernetesClient(context="x").namespace, "team")

    def test_list_secrets_pages(self):
        self.reply(
            {"items": [secret("b")], "metadata": {"continue": "tok"}},
            {"items": [secret("A", rv="7")], "metadata": {}},
        )
        items = self.client.list_secrets()
        self.assertEqual([i.secret_id for i in items], ["A", "b"])
        self.assertEqual(items[0].locations, ["apps"])
        self.assertEqual(items[0].labels, {"app": "x"})
        second = self.http.request.call_args_list[1]
        self.assertEqual(second.kwargs["query"], {"limit": "500", "continue": "tok"})
        self.assertEqual(
            self.http.request.call_args_list[0].args[1], "/api/v1/namespaces/apps/secrets"
        )

    def test_versions_and_payload(self):
        self.reply(secret())
        versions = self.client.list_versions("db@41")
        self.assertEqual((versions[0].version_id, versions[0].name), ("42", "db@42"))
        self.assertEqual(self.http.request.call_args.args[1], "/api/v1/namespaces/apps/secrets/db")
        self.reply(secret())
        self.assertEqual(self.client.access_secret_payload("db@42"), ("s3", False))
        self.reply(secret(data={"a": b64("1"), "b": b64("2")}))
        self.assertEqual(
            json.loads(self.client.access_secret_payload("db")[0]), {"a": "1", "b": "2"}
        )
        self.reply({"metadata": {"name": "e"}})
        self.assertEqual(self.client.access_secret_payload("e")[0], "{}")

    def test_create(self):
        self.reply(secret("new"))
        item = self.client.create_secret("new", '{"k": "v"}', labels={"app": "x"})
        body = self.http.request.call_args.kwargs["body"]
        self.assertEqual(body["data"], {"k": b64("v")})
        self.assertEqual(body["type"], "Opaque")
        self.assertEqual((item.secret_id, item.provider), ("new", "k8s"))
        self.reply(KubeAPIError(409, 'secrets "new" already exists'))
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.client.create_secret("new", "x")
        self.reply(KubeAPIError(422, "invalid name"))
        with self.assertRaisesRegex(RuntimeError, "invalid name"):
            self.client.create_secret("NEW", "x")

    def test_update_keeps_type_labels_and_resource_version(self):
        self.reply(
            secret(type="kubernetes.io/basic-auth") | {"type": "kubernetes.io/basic-auth"},
            secret(rv="43"),
        )
        version = self.client.add_secret_version("db@42", "newvalue")
        put = self.http.request.call_args_list[1]
        self.assertEqual(put.args[:2], ("PUT", "/api/v1/namespaces/apps/secrets/db"))
        self.assertEqual(put.kwargs["body"]["type"], "kubernetes.io/basic-auth")
        self.assertEqual(put.kwargs["body"]["metadata"]["resourceVersion"], "42")
        self.assertEqual(put.kwargs["body"]["data"], {"value": b64("newvalue")})
        self.assertEqual(version.version_id, "43")

    def test_delete(self):
        self.reply({})
        self.client.delete_secret("db@42")
        self.assertEqual(
            self.http.request.call_args.args[:2], ("DELETE", "/api/v1/namespaces/apps/secrets/db")
        )

    def test_error_translation(self):
        cases = [
            (KubeAPIError(0, "refused"), RuntimeError),
            (KubeAPIError(403, "no"), PermissionError),
            (KubeAPIError(404, ""), FileNotFoundError),
            (KubeAPIError(500, "boom"), RuntimeError),
        ]
        for error, expected in cases:
            self.reply(error)
            with self.assertRaises(expected):
                self.client.access_secret_payload("db")

    def test_expired_token_is_retried_once(self):
        fresh = MagicMock()
        fresh.request.return_value = secret()
        self.http.request.side_effect = KubeAPIError(401, "expired")
        with (
            patch("src.providers.kubernetes.client.resolve_context") as resolve,
            patch("src.providers.kubernetes.client.KubeHTTP", return_value=fresh),
        ):
            self.assertEqual(self.client.access_secret_payload("db"), ("s3", False))
            resolve.assert_called_once_with("dev")
        fresh.request.side_effect = KubeAPIError(401, "still")
        with (
            patch("src.providers.kubernetes.client.resolve_context"),
            patch("src.providers.kubernetes.client.KubeHTTP", return_value=fresh),
        ):
            with self.assertRaises(PermissionError):
                self.client.access_secret_payload("db")

    def test_configure_lock_and_dialog(self):
        self.client.configure(" prod ", " ns ")
        self.assertEqual((self.client.context, self.client.namespace), ("prod", "ns"))
        self.assertIsNone(self.client._http_client)
        self.client.configure("", "")
        self.assertIsNone(self.client._context)
        self.client._http_client = self.http
        self.client.lock()
        self.assertIsNone(self.client._http_client)
        with patch("src.providers.kubernetes.client.list_contexts", return_value=["a"]):
            self.assertEqual(self.client.available_contexts(), ["a"])
        with patch("src.ui.dialogs.show_change_kubernetes_dialog") as show:
            self.client.open_context_dialog("w", MagicMock())
        show.assert_called_once()

    def test_http_is_built_from_the_kubeconfig(self):
        client = KubernetesClient(context="dev")
        with (
            patch("src.providers.kubernetes.client.resolve_context") as resolve,
            patch("src.providers.kubernetes.client.KubeHTTP") as http,
        ):
            first = client._http()
            second = client._http()
            self.assertIs(first, second)
            resolve.assert_called_once_with("dev")
            http.assert_called_once_with(resolve.return_value)


if __name__ == "__main__":
    unittest.main()


class TestNamespaces(unittest.TestCase):
    def setUp(self):
        self.client = KubernetesClient(context="dev", namespace="apps")
        self.http = MagicMock()
        self.client._http_client = self.http

    def test_lists_sorted_names_of_the_active_context(self):
        self.http.request.return_value = {
            "items": [{"metadata": {"name": "b"}}, {"metadata": {"name": "a"}}]
        }
        self.assertEqual(self.client.list_namespaces(), ["a", "b"])
        self.assertEqual(self.http.request.call_args.args, ("GET", "/api/v1/namespaces"))

    def test_other_context_uses_its_own_connection(self):
        other = MagicMock()
        other.request.return_value = {"items": []}
        with (
            patch("src.providers.kubernetes.client.resolve_context") as resolve,
            patch("src.providers.kubernetes.client.KubeHTTP", return_value=other),
        ):
            self.assertEqual(self.client.list_namespaces("prod"), [])
            resolve.assert_called_once_with("prod")
        self.http.request.assert_not_called()

    def test_not_permitted_is_empty_other_errors_raise(self):
        for status in (401, 403, 404):
            self.http.request.side_effect = KubeAPIError(status, "no")
            self.assertEqual(self.client.list_namespaces(), [])
        self.http.request.side_effect = KubeAPIError(500, "boom")
        with self.assertRaises(RuntimeError):
            self.client.list_namespaces()
