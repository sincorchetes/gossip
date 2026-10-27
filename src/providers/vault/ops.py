"""KV version 2 operations for the Vault / OpenBao provider."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers.common import (
    SINGLE_KEY,
    format_key_values,
    parse_json_object,
    parse_rfc3339,
    split_numeric_version,
)
from src.providers.errors import CONFLICT, DENIED, MISSING, kind_for_status, provider_error
from src.providers.vault.api import VaultAPIError, VaultHTTP

MAX_DEPTH = 8
MAX_SECRETS = 5000


def parse_payload(text: str) -> Dict[str, Any]:
    """Turn the editor text into KV data: a JSON object as-is, anything else as ``value``."""
    return parse_json_object(text) or {SINGLE_KEY: text}


format_payload = format_key_values


class VaultOperationsMixin:
    """Listing, versions and CRUD over the KV v2 secrets engine."""

    mount: str

    def _http(self) -> VaultHTTP: ...  # type: ignore[empty-body]

    def _call(self, method: str, path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """Run a request translating API failures into the exceptions the UI understands."""
        try:
            return self._http().request(method, path, **kwargs)
        except VaultAPIError as exc:
            detail = "; ".join(exc.errors) or str(exc)
            kind = kind_for_status(exc.status)
            if exc.status == 0:
                message = _("Could not reach Vault: {detail}").format(detail=detail)
            elif kind == DENIED:
                message = _("Vault denied access ({status}): {detail}").format(
                    status=exc.status, detail=detail
                )
            elif kind == MISSING:
                message = detail or _("Not found in Vault.")
            else:
                message = _("Vault error: {detail}").format(detail=detail)
            raise provider_error(kind, message, "vault", exc) from exc

    def _list_keys(self, prefix: str) -> List[str]:
        """Keys directly below ``prefix`` (folders end with '/'); empty when it does not exist."""
        try:
            resp = self._call("GET", f"{self.mount}/metadata/{prefix}", query={"list": "true"})
        except FileNotFoundError:
            return []
        return list((resp or {}).get("data", {}).get("keys", []))

    def list_secrets(self) -> List[SecretItem]:
        """Walk the mount and list every secret path."""
        names: List[str] = []
        pending = [("", 0)]
        while pending and len(names) < MAX_SECRETS:
            prefix, depth = pending.pop()
            for key in self._list_keys(prefix):
                if key.endswith("/"):
                    if depth + 1 < MAX_DEPTH:
                        pending.append((prefix + key, depth + 1))
                else:
                    names.append(prefix + key)

        secrets = [
            SecretItem(
                name=path,
                secret_id=path,
                provider="vault",
                replication_type="AUTOMATIC",
                locations=[self.mount],
            )
            for path in names[:MAX_SECRETS]
        ]
        secrets.sort(key=lambda s: s.secret_id.lower())
        return secrets

    def list_versions(self, secret_name: str) -> List[SecretVersionItem]:
        """List the stored versions of a secret, newest first."""
        path, _version = split_numeric_version(secret_name)
        meta = (self._call("GET", f"{self.mount}/metadata/{path}") or {}).get("data", {})
        versions: List[SecretVersionItem] = []
        for number, info in meta.get("versions", {}).items():
            if info.get("destroyed"):
                state = "DESTROYED"
            elif parse_rfc3339(info.get("deletion_time")):
                state = "DISABLED"
            else:
                state = "ENABLED"
            versions.append(
                SecretVersionItem(
                    version_id=str(number),
                    name=f"{path}@{number}",
                    state=state,
                    create_time=parse_rfc3339(info.get("created_time")),
                    destroy_time=parse_rfc3339(info.get("deletion_time")),
                )
            )
        versions.sort(key=lambda v: int(v.version_id), reverse=True)
        return versions

    def access_secret_payload(
        self, secret_name: str, version: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Read a secret (a specific version when given) as editable text."""
        path, number = split_numeric_version(secret_name, version)
        query = {"version": number} if number else None
        try:
            resp = self._call("GET", f"{self.mount}/data/{path}", query=query)
        except FileNotFoundError as exc:
            raise provider_error(
                MISSING,
                _(
                    "The secret '{secret}' or that version does not exist (it may be disabled)."
                ).format(secret=path),
                "vault",
                exc,
            ) from exc
        data = ((resp or {}).get("data") or {}).get("data")
        if data is None:
            raise provider_error(
                MISSING, _("The version of '{secret}' has no data.").format(secret=path), "vault"
            )
        return format_payload(data), False

    def _write(self, path: str, data: Dict[str, Any], cas: Optional[int] = None) -> Dict[str, Any]:
        """Store a new version, optionally only if the current version matches ``cas``."""
        body: Dict[str, Any] = {"data": data}
        if cas is not None:
            body["options"] = {"cas": cas}
        resp = self._call("POST", f"{self.mount}/data/{path}", body=body)
        return (resp or {}).get("data", {})

    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        """Create a secret, refusing to overwrite an existing one."""
        try:
            meta = self._write(secret_id, parse_payload(payload_data), cas=0)
        except RuntimeError as exc:
            if "check-and-set" in str(exc):
                raise provider_error(
                    CONFLICT,
                    _(
                        "The secret '{secret}' already exists. Use 'New Version' to modify it."
                    ).format(secret=secret_id),
                    "vault",
                    exc,
                ) from exc
            raise
        if labels:
            self._call(
                "POST", f"{self.mount}/metadata/{secret_id}", body={"custom_metadata": labels}
            )
        return SecretItem(
            name=secret_id,
            secret_id=secret_id,
            provider="vault",
            create_time=parse_rfc3339(meta.get("created_time")) or datetime.now(),
            labels=dict(labels or {}),
            locations=[self.mount],
        )

    def load_metadata(self, secret: SecretItem) -> Tuple[Dict[str, str], Optional[str]]:
        """Read the custom metadata of a secret (the listing does not include it)."""
        meta = (self._call("GET", f"{self.mount}/metadata/{secret.name}") or {}).get("data", {})
        return {str(k): str(v) for k, v in (meta.get("custom_metadata") or {}).items()}, None

    def update_metadata(
        self, secret_name: str, labels: Dict[str, str], description: Optional[str]
    ) -> None:
        """Replace the custom metadata of a secret."""
        path, _version = split_numeric_version(secret_name)
        self._call("POST", f"{self.mount}/metadata/{path}", body={"custom_metadata": labels})

    def add_secret_version(self, secret_name: str, payload_data: str) -> SecretVersionItem:
        """Write a new version of an existing secret."""
        path, _version = split_numeric_version(secret_name)
        meta = self._write(path, parse_payload(payload_data))
        number = str(meta.get("version", ""))
        return SecretVersionItem(
            version_id=number,
            name=f"{path}@{number}",
            state="ENABLED",
            create_time=parse_rfc3339(meta.get("created_time")) or datetime.now(),
        )

    def delete_secret(self, secret_name_or_id: str) -> None:
        """Delete a secret with its metadata and every version."""
        path, _version = split_numeric_version(secret_name_or_id)
        self._call("DELETE", f"{self.mount}/metadata/{path}")

    def _version_action(self, action: str, version_name: str) -> None:
        """Apply delete / undelete / destroy to one version."""
        path, number = split_numeric_version(version_name)
        if not number:
            raise ValueError(_("A version number is required."))
        self._call("POST", f"{self.mount}/{action}/{path}", body={"versions": [int(number)]})

    def toggle_version_state(self, version: Any, enable: bool) -> None:
        """Disable (soft-delete) or re-enable (undelete) a version."""
        name = getattr(version, "name", version)
        self._version_action("undelete" if enable else "delete", name)

    def destroy_version(self, version: Any) -> None:
        """Permanently destroy the data of a version."""
        self._version_action("destroy", getattr(version, "name", version))
