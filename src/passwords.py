"""Random password generation with the standard library's cryptographic generator."""

from __future__ import annotations

import secrets
import string
from typing import List

LOWER = string.ascii_lowercase
UPPER = string.ascii_uppercase
DIGITS = string.digits
SYMBOLS = "!@#$%^&*()-_=+[]{}:;,.?/~"
AMBIGUOUS = frozenset("0O1lI|")

MIN_LENGTH = 8
MAX_LENGTH = 128
DEFAULT_LENGTH = 24


def generate_password(
    length: int = DEFAULT_LENGTH,
    lower: bool = True,
    upper: bool = True,
    digits: bool = True,
    symbols: bool = True,
    avoid_ambiguous: bool = False,
) -> str:
    """Generate a random password containing at least one character of each enabled kind.

    Args:
        length: Number of characters (MIN_LENGTH to MAX_LENGTH).
        lower: Include lowercase letters.
        upper: Include uppercase letters.
        digits: Include digits.
        symbols: Include punctuation symbols.
        avoid_ambiguous: Leave out characters that look alike (0 O 1 l I |).

    Returns:
        str: The generated password.

    Raises:
        ValueError: If no character kind is enabled or the length is out of range.
    """
    if not MIN_LENGTH <= length <= MAX_LENGTH:
        raise ValueError(f"length must be between {MIN_LENGTH} and {MAX_LENGTH}")
    pools: List[str] = []
    for enabled, characters in (
        (lower, LOWER),
        (upper, UPPER),
        (digits, DIGITS),
        (symbols, SYMBOLS),
    ):
        if enabled:
            kept = "".join(c for c in characters if not (avoid_ambiguous and c in AMBIGUOUS))
            pools.append(kept)
    if not pools:
        raise ValueError("enable at least one kind of character")

    chosen = [secrets.choice(pool) for pool in pools]
    everything = "".join(pools)
    chosen.extend(secrets.choice(everything) for _ in range(length - len(chosen)))
    secrets.SystemRandom().shuffle(chosen)
    return "".join(chosen)
