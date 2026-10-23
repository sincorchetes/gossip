"""Data parsing helpers for AWS Secrets Manager items and versions."""

from __future__ import annotations

from typing import Dict

from src.models import SecretItem, SecretVersionItem


def parse_aws_secret_item(secret: dict) -> SecretItem:
    """Convert an AWS Secrets Manager secret dictionary into a normalized SecretItem.

    Args:
        secret: Dictionary returned in SecretList from list_secrets.

    Returns:
        SecretItem: Normalized secret metadata instance.
    """
    name = secret.get("ARN", secret.get("Name", ""))
    secret_id = secret.get("Name", "")
    desc = secret.get("Description")
    created_dt = secret.get("CreatedDate")
    last_changed = secret.get("LastChangedDate")

    tags_dict: Dict[str, str] = {}
    for tag in secret.get("Tags", []):
        k = tag.get("Key")
        v = tag.get("Value", "")
        if k:
            tags_dict[k] = v

    repl_status = secret.get("ReplicationStatus", [])
    locations = [r.get("Region") for r in repl_status if r.get("Region")]
    repl_type = "REPLICATED" if locations else "SINGLE_REGION"

    return SecretItem(
        name=name,
        secret_id=secret_id,
        provider="aws",
        description=desc,
        create_time=created_dt,
        last_changed_date=last_changed,
        labels=tags_dict,
        replication_type=repl_type,
        locations=locations,
        kms_key_id=secret.get("KmsKeyId"),
    )


def parse_aws_version_item(v: dict, actual_secret_id: str) -> SecretVersionItem:
    """Convert an AWS version dictionary into a normalized SecretVersionItem.

    Args:
        v: Version metadata dictionary from list_secret_version_ids.
        actual_secret_id: Base secret identifier name.

    Returns:
        SecretVersionItem: Normalized secret version instance.
    """
    vid = v.get("VersionId", "")
    stages = v.get("VersionStages", [])
    created_dt = v.get("CreatedDate")
    state_str = stages[0] if stages else "DEPRECATED"

    return SecretVersionItem(
        version_id=vid,
        name=f"{actual_secret_id}@{vid}",
        state=state_str,
        stages=stages,
        create_time=created_dt,
        destroy_time=None,
    )
