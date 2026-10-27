"""HashiCorp Vault / OpenBao (KV v2) provider package."""

from src.providers.vault.client import VaultClient
from src.providers.vault.discovery import normalize_address, normalize_mount

__all__ = ["VaultClient", "normalize_address", "normalize_mount"]
