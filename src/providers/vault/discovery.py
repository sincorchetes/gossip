"""Discovery of the Vault / OpenBao server address, token and TLS settings."""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlsplit

from src.i18n import _
from src.log import get_logger

log = get_logger(__name__)

DEFAULT_MOUNT = "secret"
_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


def _first_env(*names: str) -> Optional[str]:
    """Return the first non-empty environment variable among ``names``."""
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def detect_address() -> Optional[str]:
    """Server address from VAULT_ADDR or BAO_ADDR."""
    return _first_env("VAULT_ADDR", "BAO_ADDR")


def detect_namespace() -> Optional[str]:
    """Enterprise / OpenBao namespace from VAULT_NAMESPACE or BAO_NAMESPACE."""
    return _first_env("VAULT_NAMESPACE", "BAO_NAMESPACE")


def detect_cafile() -> Optional[str]:
    """Custom CA bundle from VAULT_CACERT or BAO_CACERT."""
    return _first_env("VAULT_CACERT", "BAO_CACERT")


def detect_token() -> Optional[str]:
    """Token from VAULT_TOKEN / BAO_TOKEN or the CLI's ``~/.vault-token`` file."""
    token = _first_env("VAULT_TOKEN", "BAO_TOKEN")
    if token:
        return token
    for name in (".vault-token", ".bao-token"):
        path = os.path.join(os.path.expanduser("~"), name)
        try:
            with open(path, encoding="utf-8") as handle:
                content = handle.read().strip()
        except OSError:
            continue
        if content:
            return content
    return None


def normalize_address(address: str) -> str:
    """Validate a server address and return it without a trailing slash.

    Tokens travel in a header, so plain HTTP is only accepted for loopback hosts.

    Raises:
        ValueError: If the address is not an https URL (or http on loopback).
    """
    clean = address.strip().rstrip("/")
    parts = urlsplit(clean)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(
            _(
                "Invalid Vault address '{address}'. Use a URL such as https://vault.example.com:8200."
            ).format(address=address)
        )
    if parts.scheme == "http" and parts.hostname not in _LOOPBACK_HOSTS:
        raise ValueError(
            _(
                "Refusing to send the Vault token over plain HTTP to '{host}'. "
                "Use an https:// address."
            ).format(host=parts.hostname)
        )
    return clean


def normalize_mount(mount: Optional[str]) -> str:
    """Return the secrets engine mount path without surrounding slashes."""
    return (mount or "").strip().strip("/") or DEFAULT_MOUNT
