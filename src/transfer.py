"""Export and import of secrets between providers and portable JSON files.

Export files are JSON documents:

    {"format": "gossip-export", "version": 1, "provider": "gcp", "exported_at": "...",
     "includes_values": false,
     "secrets": [{"id": "db_password", "description": "...", "labels": {"env": "prod"},
                  "value": "..."}]}

Imports also accept a plain ``{id: value}`` mapping. Existing secrets are never overwritten.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import yaml

from src.i18n import _
from src.models import SecretItem

FORMAT_NAME = "gossip-export"
FORMAT_VERSION = 1
SKIP_EXISTING = "skip"
NEW_VERSION = "version"
MAX_IMPORT_ENTRIES = 1000
MAX_IMPORT_BYTES = 5 * 1024 * 1024

ProgressCallback = Callable[[int, int], None]


@dataclass
class TransferEntry:
    """A secret as stored in an export/import file.

    Attributes:
        secret_id: Short secret name.
        value: Plaintext value, or None when the file carries no values. Structured Ansible
            values (dictionaries and lists) are kept as native JSON objects on export.
        description: Optional description.
        labels: Optional key/value labels.
    """

    secret_id: str
    value: Any = None
    description: Optional[str] = None
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ImportResult:
    """Outcome of an import run.

    Attributes:
        created: Ids of secrets that were created.
        updated: Ids of existing secrets that received a new version.
        skipped: Ids skipped because they already exist (and no new version was requested).
        failed: (id, error message) pairs for secrets the provider rejected.
    """

    created: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)
    updated: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
_NATIVE_TYPES = ("dict", "list", "int", "float", "bool")


def _native_value(secret: SecretItem, value: str) -> Any:
    """Return structured Ansible values as native objects instead of their YAML text.

    The Ansible provider reports dictionaries and lists as YAML text and tags each variable
    with its Python type in the "type" label; restoring the object keeps the structure when the
    file is imported again.

    Args:
        secret: Secret being exported.
        value: Value as returned by the provider.

    Returns:
        Any: A dict, list, int, float or bool for typed Ansible variables, otherwise the text.
    """
    if secret.provider != "ansible" or secret.labels.get("type") not in _NATIVE_TYPES:
        return value
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError:
        return value
    return parsed if isinstance(parsed, (dict, list, int, float, bool)) else value


def collect_export_entries(
    client: Any,
    secrets: List[SecretItem],
    include_values: bool,
    progress: Optional[ProgressCallback] = None,
) -> Tuple[List[TransferEntry], List[str]]:
    """Read secrets (and optionally their latest values) from a provider.

    Args:
        client: Provider exposing list_versions and access_secret_payload.
        secrets: Secrets to export.
        include_values: Whether to fetch each secret's latest value.
        progress: Optional callback receiving (done, total).

    Returns:
        Tuple[List[TransferEntry], List[str]]: Exported entries and 'id: error' messages for
        secrets whose value could not be read (those are exported without a value).
    """
    entries: List[TransferEntry] = []
    errors: List[str] = []
    total = len(secrets)
    for index, secret in enumerate(secrets, start=1):
        value: Optional[str] = None
        if include_values:
            try:
                versions = client.list_versions(secret.name)
                value = client.access_secret_payload(versions[0].name)[0] if versions else ""
                value = _native_value(secret, value)
            except Exception as exc:
                errors.append(f"{secret.secret_id}: {exc}")
        entries.append(
            TransferEntry(
                secret_id=secret.secret_id,
                value=value,
                description=secret.description,
                labels=dict(secret.labels),
            )
        )
        if progress:
            progress(index, total)
    return entries, errors


def build_export_document(
    provider_id: str,
    entries: List[TransferEntry],
    include_values: bool,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Build the JSON-serialisable export document.

    Args:
        provider_id: Provider the secrets come from ('gcp', 'aws', ...).
        entries: Entries to include.
        include_values: Whether values are part of the file.
        now: Timestamp override (for tests).

    Returns:
        Dict[str, Any]: Document ready for json.dump.
    """
    stamp = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    secrets: List[Dict[str, Any]] = []
    for entry in entries:
        item: Dict[str, Any] = {"id": entry.secret_id}
        if entry.description:
            item["description"] = entry.description
        if entry.labels:
            item["labels"] = entry.labels
        if include_values and entry.value is not None:
            item["value"] = entry.value
        secrets.append(item)
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "provider": provider_id,
        "exported_at": stamp,
        "includes_values": include_values,
        "secrets": secrets,
    }


def write_export_file(path: str, document: Dict[str, Any]) -> None:
    """Write an export document atomically, readable only by the owner.

    Args:
        path: Destination file path.
        document: Document produced by build_export_document.
    """
    temp_path = f"{path}.tmp"
    fd = os.open(
        temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0), 0o600
    )
    with os.fdopen(fd, "wb") as handle:
        handle.write(json.dumps(document, indent=2, ensure_ascii=False).encode("utf-8"))
        handle.write(b"\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_path, path)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
def _normalize_value(value: Any) -> Any:
    """Keep imported values with their type (text, number, boolean, object, list)."""
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return value
    return str(value)


def _as_text(value: Any) -> str:
    """Render an imported value as the text providers other than Ansible store."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _parse_labels(raw: Any, index: int) -> Dict[str, str]:
    """Validate and normalise the labels of one imported entry."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(_("Entry %d is invalid: labels must be a key/value mapping.") % index)
    return {str(k): str(v) for k, v in raw.items()}


def _parse_entry(raw: Any, index: int) -> TransferEntry:
    """Convert one item of the 'secrets' list into a TransferEntry."""
    if not isinstance(raw, dict):
        raise ValueError(_("Entry %d is invalid: expected an object.") % index)
    secret_id = raw.get("id") or raw.get("secret_id") or raw.get("name")
    if not isinstance(secret_id, str) or not secret_id.strip():
        raise ValueError(_("Entry %d is invalid: missing secret id.") % index)
    description = raw.get("description")
    return TransferEntry(
        secret_id=secret_id.strip(),
        value=_normalize_value(raw.get("value")),
        description=str(description) if description else None,
        labels=_parse_labels(raw.get("labels"), index),
    )


def _load_document(text: str) -> Any:
    """Decode JSON with the JSON parser (YAML cannot join \\ud83d\\ude00-style surrogate pairs)."""
    if text.lstrip()[:1] in ("{", "["):
        try:
            return json.loads(text)
        except ValueError:
            pass  # may still be flow-style YAML
    return yaml.safe_load(text)


def parse_import_text(text: str) -> List[TransferEntry]:
    """Parse the contents of an import file (JSON or YAML).

    Args:
        text: File contents.

    Returns:
        List[TransferEntry]: Entries to import, without duplicate ids (first one wins).

    Raises:
        ValueError: If the file is empty, malformed or too large. Messages never quote the
            file contents, which may hold secret values.
    """
    if not text.strip():
        raise ValueError(_("The import file is empty."))
    try:
        data = _load_document(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        raise ValueError(_("The import file is not valid JSON or YAML") + where) from exc

    if isinstance(data, dict) and isinstance(data.get("secrets"), list):
        entries = [_parse_entry(raw, i) for i, raw in enumerate(data["secrets"], start=1)]
    elif isinstance(data, dict) and data and all(isinstance(k, str) for k in data):
        entries = [
            TransferEntry(secret_id=k.strip(), value=_normalize_value(v)) for k, v in data.items()
        ]
    else:
        raise ValueError(
            _("Unrecognised import file: expected a 'secrets' list or an id/value mapping.")
        )

    unique: List[TransferEntry] = []
    seen: Set[str] = set()
    for entry in entries:
        if entry.secret_id and entry.secret_id not in seen:
            seen.add(entry.secret_id)
            unique.append(entry)
    if not unique:
        raise ValueError(_("The import file contains no secrets."))
    if len(unique) > MAX_IMPORT_ENTRIES:
        raise ValueError(_("Too many secrets in one import (maximum %d).") % MAX_IMPORT_ENTRIES)
    return unique


def read_import_file(path: str) -> List[TransferEntry]:
    """Read and parse an import file, refusing unreasonably large ones.

    Args:
        path: Path of the file chosen by the user.

    Returns:
        List[TransferEntry]: Parsed entries.

    Raises:
        ValueError: If the file is too large or its contents are invalid.
        OSError: If the file cannot be read.
    """
    if os.path.getsize(path) > MAX_IMPORT_BYTES:
        raise ValueError(_("The import file is too large."))
    with open(path, "r", encoding="utf-8") as handle:
        return parse_import_text(handle.read())


def import_entries(
    client: Any,
    entries: List[TransferEntry],
    existing_ids: Set[str],
    progress: Optional[ProgressCallback] = None,
    on_existing: str = SKIP_EXISTING,
    existing_names: Optional[Dict[str, str]] = None,
) -> ImportResult:
    """Create secrets on a provider; existing ones are skipped or get a new version.

    Existing secrets are never overwritten: with ``on_existing="version"`` their value is
    saved as a new version (so the previous one is kept), and entries without a value are
    skipped.

    Args:
        client: Provider exposing create_secret (and add_secret_version for new versions).
        entries: Entries to import.
        existing_ids: Ids already present in the target provider.
        progress: Optional callback receiving (done, total).
        on_existing: SKIP_EXISTING or NEW_VERSION.
        existing_names: Id to full resource name of the existing secrets (defaults to the id).

    Returns:
        ImportResult: Which secrets were created, updated, skipped or failed.
    """
    native_create = getattr(client, "create_native_secret", None)
    result = ImportResult()
    total = len(entries)
    for index, entry in enumerate(entries, start=1):
        if entry.secret_id in existing_ids:
            if on_existing == NEW_VERSION and entry.value is not None:
                try:
                    name = (existing_names or {}).get(entry.secret_id, entry.secret_id)
                    client.add_secret_version(name, _as_text(entry.value))
                    result.updated.append(entry.secret_id)
                except Exception as exc:
                    result.failed.append((entry.secret_id, str(exc)))
            else:
                result.skipped.append(entry.secret_id)
        else:
            try:
                if native_create is not None and not isinstance(entry.value, (str, type(None))):
                    native_create(
                        entry.secret_id,
                        entry.value,
                        labels=entry.labels or None,
                        description=entry.description,
                    )
                else:
                    client.create_secret(
                        entry.secret_id,
                        _as_text(entry.value),
                        labels=entry.labels or None,
                        description=entry.description,
                    )
                result.created.append(entry.secret_id)
            except Exception as exc:
                result.failed.append((entry.secret_id, str(exc)))
        if progress:
            progress(index, total)
    return result
