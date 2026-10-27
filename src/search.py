"""Query parsing and matching for the secrets sidebar search box.

Syntax (case-insensitive, words are combined with AND):
    db password        every word must appear in the name, description or a label
    label:env          the secret has a label named 'env'
    label:env=prod     the label 'env' has exactly the value 'prod'
    -legacy            the word must NOT appear
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from src.models import SecretItem

_LABEL_PREFIXES = ("label:", "tag:")

LabelFilter = Tuple[str, Optional[str]]


def parse_query(text: str) -> Tuple[List[str], List[str], List[LabelFilter]]:
    """Split a search string into included words, excluded words and label filters.

    Args:
        text: Raw text typed in the search box.

    Returns:
        Tuple[List[str], List[str], List[LabelFilter]]: (words, excluded words,
        (label key, optional label value) filters), all lowercased.
    """
    words: List[str] = []
    excluded: List[str] = []
    labels: List[LabelFilter] = []
    for token in text.lower().split():
        prefix = next((p for p in _LABEL_PREFIXES if token.startswith(p)), None)
        if prefix:
            spec = token[len(prefix) :]
            if not spec:
                continue
            key, sep, value = spec.partition("=")
            labels.append((key, value if sep else None))
        elif token.startswith("-") and len(token) > 1:
            excluded.append(token[1:])
        elif token != "-":
            words.append(token)
    return words, excluded, labels


def _haystack(secret: SecretItem) -> str:
    """Return the searchable text of a secret: name, description and labels."""
    parts = [secret.secret_id, secret.description or ""]
    for key, value in secret.labels.items():
        parts.extend((key, value))
    return "\n".join(parts).lower()


def matches_query(secret: SecretItem, text: str) -> bool:
    """Check whether a secret satisfies a search string.

    Args:
        secret: Secret to test.
        text: Raw text typed in the search box (empty matches everything).

    Returns:
        bool: True if the secret should be shown.
    """
    words, excluded, label_filters = parse_query(text)
    if not (words or excluded or label_filters):
        return True

    haystack = _haystack(secret)
    if any(word not in haystack for word in words):
        return False
    if any(word in haystack for word in excluded):
        return False

    labels = {k.lower(): v.lower() for k, v in secret.labels.items()}
    for key, value in label_filters:
        if key not in labels:
            return False
        if value is not None and labels[key] != value:
            return False
    return True
