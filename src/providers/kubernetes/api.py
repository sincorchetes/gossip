"""Minimal HTTP client for the Kubernetes API (standard library only)."""

from __future__ import annotations

import json
import os
import ssl
import tempfile
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

from src.providers.kubernetes.kubeconfig import ClusterAccess

REQUEST_TIMEOUT = 15


class KubeAPIError(Exception):
    """Error answered by the API server (status 0 for network failures)."""

    def __init__(self, status: int, message: str):
        super().__init__(message or f"HTTP {status}")
        self.status = status
        self.message = message


def build_ssl_context(access: ClusterAccess) -> ssl.SSLContext:
    """TLS context trusting the cluster CA and presenting the client certificate, if any."""
    context = (
        ssl.create_default_context(cadata=access.ca_pem)
        if access.ca_pem
        else (ssl.create_default_context())
    )
    if access.cert_pem and access.key_pem:
        # load_cert_chain only reads files; keep them private and short-lived
        with tempfile.TemporaryDirectory() as folder:
            cert_path = os.path.join(folder, "cert.pem")
            key_path = os.path.join(folder, "key.pem")
            for path, content in ((cert_path, access.cert_pem), (key_path, access.key_pem)):
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(content)
            context.load_cert_chain(cert_path, key_path)
    return context


class KubeHTTP:
    """Authenticated JSON requests against one cluster."""

    def __init__(self, access: ClusterAccess):
        self.access = access
        self._context = build_ssl_context(access)

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send a request and return the decoded JSON body.

        Raises:
            KubeAPIError: On HTTP errors and connection failures.
        """
        url = f"{self.access.server}{quote(path, safe='/')}"
        if query:
            url += "?" + urlencode(query)
        headers = {"Accept": "application/json"}
        if self.access.token:
            headers["Authorization"] = f"Bearer {self.access.token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT, context=self._context) as r:
                raw = r.read()
        except urllib.error.HTTPError as exc:
            raise KubeAPIError(exc.code, _status_message(exc)) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise KubeAPIError(0, str(getattr(exc, "reason", exc))) from exc
        return json.loads(raw) if raw else {}


def _status_message(exc: urllib.error.HTTPError) -> str:
    """The ``message`` of a Kubernetes Status error response, if present."""
    try:
        return str(json.loads(exc.read() or b"{}").get("message", ""))
    except Exception:
        return ""
