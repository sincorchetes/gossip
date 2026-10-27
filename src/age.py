"""How long ago a secret last changed, to flag the ones that were never rotated."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from src.models import SecretItem

STALE_ENV = "GOSSIP_STALE_DAYS"
DEFAULT_STALE_DAYS = 90


def stale_days() -> int:
    """Days without change after which a secret is flagged (0 disables the flag).

    Read from GOSSIP_STALE_DAYS; invalid values fall back to the default of 90.
    """
    raw = os.environ.get(STALE_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_STALE_DAYS
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_STALE_DAYS


def age_days(secret: SecretItem, now: Optional[datetime] = None) -> Optional[int]:
    """Whole days since the secret last changed (its creation if it never changed).

    Args:
        secret: The secret to measure.
        now: Reference time, for tests; defaults to the current time.

    Returns:
        Optional[int]: The age, or None when the provider reports no date.
    """
    moment = secret.last_changed_date or secret.create_time
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    return max(0, (reference - moment).days)


def is_stale(secret: SecretItem, now: Optional[datetime] = None) -> bool:
    """True when the secret is older than the configured threshold."""
    limit = stale_days()
    days = age_days(secret, now)
    return bool(limit) and days is not None and days >= limit
