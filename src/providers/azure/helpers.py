"""Data parsing helpers for Azure Key Vault secret items and versions."""

from __future__ import annotations

from typing import Any, Optional

from src.models import SecretItem, SecretVersionItem


def parse_azure_secret_item(prop: Any, vault_url: Optional[str]) -> SecretItem:
    """Convert an Azure Key Vault SecretProperties object into a normalized SecretItem.

    Args:
        prop: SecretProperties object returned from list_properties_of_secrets.
        vault_url: Target Key Vault endpoint URL.

    Returns:
        SecretItem: Normalized secret representation.
    """
    sec_id = prop.name
    tags_dict = dict(prop.tags) if prop.tags else {}
    content_type = prop.content_type

    return SecretItem(
        name=prop.id or f"{vault_url}secrets/{sec_id}",
        secret_id=sec_id,
        provider="azure",
        description=content_type,
        create_time=prop.created_on,
        last_changed_date=prop.updated_on,
        labels=tags_dict,
        replication_type="AUTOMATIC",
        locations=[],
    )


def parse_azure_version_item(prop: Any, actual_name: str) -> SecretVersionItem:
    """Convert an Azure SecretProperties version object into a SecretVersionItem.

    Args:
        prop: SecretProperties object from list_properties_of_secret_versions.
        actual_name: Base secret identifier string.

    Returns:
        SecretVersionItem: Normalized secret version instance.
    """
    vid = prop.version or ""
    state_str = "ENABLED" if prop.enabled else "DISABLED"

    return SecretVersionItem(
        version_id=vid,
        name=f"{actual_name}@{vid}",
        state=state_str,
        stages=[],
        create_time=prop.created_on,
        destroy_time=None,
    )
