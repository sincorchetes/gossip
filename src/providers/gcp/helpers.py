"""Helper data parsers and conversion utilities for GCP Secret Manager."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from google.cloud import secretmanager_v1

from src.models import SecretItem, SecretVersionItem


def _parse_timestamp(ts: Any) -> Optional[datetime]:
    """Safely convert GCP timestamps to standard Python datetime instances.

    Args:
        ts: Raw timestamp object (DatetimeWithNanoseconds, protobuf Timestamp, or datetime).

    Returns:
        Optional[datetime]: Converted datetime instance or None if input was None.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if hasattr(ts, "ToDatetime"):
        return ts.ToDatetime()
    if hasattr(ts, "to_datetime"):
        return ts.to_datetime()
    return None


def parse_secret_item(secret: Any) -> SecretItem:
    """Convert a GCP Secret protobuf object into a normalized SecretItem.

    Args:
        secret: GCP Secret protobuf message.

    Returns:
        SecretItem: Normalized secret representation.
    """
    secret_id = secret.name.split("/")[-1]
    create_dt = _parse_timestamp(secret.create_time)

    repl_type = "AUTOMATIC"
    locations = []
    if secret.replication.automatic:
        repl_type = "AUTOMATIC"
    elif secret.replication.user_managed:
        repl_type = "USER_MANAGED"
        locations = [replica.location for replica in secret.replication.user_managed.replicas]

    return SecretItem(
        name=secret.name,
        secret_id=secret_id,
        create_time=create_dt,
        labels=dict(secret.labels) if secret.labels else {},
        replication_type=repl_type,
        locations=locations,
    )


def parse_version_item(version: Any) -> SecretVersionItem:
    """Convert a GCP SecretVersion protobuf object into a SecretVersionItem.

    Args:
        version: GCP SecretVersion protobuf message.

    Returns:
        SecretVersionItem: Normalized secret version representation.
    """
    version_id = version.name.split("/")[-1]
    state_str = secretmanager_v1.SecretVersion.State(version.state).name
    return SecretVersionItem(
        version_id=version_id,
        name=version.name,
        state=state_str,
        create_time=_parse_timestamp(version.create_time),
        destroy_time=_parse_timestamp(version.destroy_time),
    )
