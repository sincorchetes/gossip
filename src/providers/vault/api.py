"""Minimal HTTP client for the Vault / OpenBao KV version 2 API (standard library only)."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode

REQUEST_TIMEOUT = 15


class VaultAPIError(Exception):
    """Error answered by the server (or a network failure when ``status`` is 0)."""

    def __init__(self, status: int, errors: list[str]):
        super().__init__("; ".join(errors) or f"HTTP {status}")
        self.status = status
        self.errors = errors


class VaultHTTP:
    """Authenticated JSON requests against one Vault / OpenBao server."""

    def __init__(
        self,
        address: str,
        token: str,
        namespace: Optional[str] = None,
        cafile: Optional[str] = None,
    ):
        self.address = address
        self._token = token
        self._namespace = namespace
        self._context = ssl.create_default_context(cafile=cafile) if cafile else None

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Send a request to ``/v1/<path>`` and return the decoded JSON body.

        Args:
            method: HTTP method.
            path: API path below ``/v1/``; segments are percent-encoded.
            body: Optional JSON payload.
            query: Optional query-string parameters.

        Returns:
            Optional[Dict[str, Any]]: Decoded response, or None for an empty body.

        Raises:
            VaultAPIError: On HTTP errors and connection failures.
        """
        url = f"{self.address}/v1/{quote(path, safe='/')}"
        if query:
            url += "?" + urlencode(query)
        headers = {"X-Vault-Token": self._token, "Accept": "application/json"}
        if self._namespace:
            headers["X-Vault-Namespace"] = self._namespace
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(
                req, timeout=REQUEST_TIMEOUT, context=self._context
            ) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            raise VaultAPIError(exc.code, _error_messages(exc)) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise VaultAPIError(0, [str(getattr(exc, "reason", exc))]) from exc
        return json.loads(raw) if raw else None


def _error_messages(exc: urllib.error.HTTPError) -> list[str]:
    """Extract the ``errors`` list from an error response, if it has one."""
    try:
        payload = json.loads(exc.read() or b"{}")
        return [str(e) for e in payload.get("errors", [])]
    except Exception:
        return []
