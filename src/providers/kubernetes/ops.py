"""Secret operations for the Kubernetes provider."""

from __future__ import annotations

import base64
import binascii
from typing import Any, Dict, List, Optional, Tuple

from src.exceptions import SecretConflictError
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
from src.providers.kubernetes.api import KubeAPIError, KubeHTTP

PAGE_SIZE = "500"
_BASE64 = "base64:"


def strip_version(name: str) -> str:
    """Drop the ``@<resourceVersion>`` suffix produced by list_versions."""
    return split_numeric_version(name)[0]


def decode_data(data: Dict[str, str]) -> Dict[str, str]:
    """Decode the base64 values of a Secret; binary values are shown as ``base64:<text>``."""
    decoded: Dict[str, str] = {}
    for key, value in data.items():
        raw = base64.b64decode(value)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = _BASE64 + value
        else:
            if text.startswith(_BASE64):
                text = _BASE64 + value
        decoded[key] = text
    return decoded


def encode_data(values: Dict[str, str]) -> Dict[str, str]:
    """Inverse of decode_data: base64-encode every value for the API."""
    encoded: Dict[str, str] = {}
    for key, text in values.items():
        if text.startswith(_BASE64):
            try:
                base64.b64decode(text[len(_BASE64) :], validate=True)
            except binascii.Error as exc:
                raise ValueError(
                    _("The value of '{key}' starts with 'base64:' but is not valid base64.").format(
                        key=key
                    )
                ) from exc
            encoded[key] = text[len(_BASE64) :]
        else:
            encoded[key] = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return encoded


def parse_payload(text: str) -> Dict[str, str]:
    """Editor text to Secret keys: a JSON object of strings as-is, anything else under ``value``."""
    obj = parse_json_object(text)
    if obj is None:
        return {SINGLE_KEY: text}
    if not all(isinstance(v, str) for v in obj.values()):
        raise ValueError(_("Kubernetes Secret values must be strings."))
    return obj


format_payload = format_key_values


class KubernetesOperationsMixin:
    """Listing and CRUD over the Secrets of one namespace."""

    namespace: str

    def _http(self) -> KubeHTTP: ...  # type: ignore[empty-body]

    def _invalidate(self) -> None: ...

    def _call(self, method: str, path: str, **kwargs: Any) -> Dict[str, Any]:
        """Run a request, retrying once after a 401 (expired token) and translating errors."""
        for attempt in (1, 2):
            try:
                return self._http().request(method, path, **kwargs)
            except KubeAPIError as exc:
                if exc.status == 401 and attempt == 1:
                    self._invalidate()
                    continue
                raise self._translate(exc) from exc
        raise AssertionError("unreachable")  # pragma: no cover

    def _translate(self, exc: KubeAPIError) -> Exception:
        kind = kind_for_status(exc.status)
        if exc.status == 0:
            message = _("Could not reach the cluster: {detail}").format(detail=exc.message)
        elif kind == DENIED:
            message = _("Kubernetes denied access ({status}): {detail}").format(
                status=exc.status, detail=exc.message
            )
        elif kind == MISSING:
            message = exc.message or _("Not found in the cluster.")
        else:
            message = _("Kubernetes error: {detail}").format(detail=exc.message)
        return provider_error(kind, message, "k8s", exc)

    @property
    def _collection(self) -> str:
        return f"/api/v1/namespaces/{self.namespace}/secrets"

    def _item(self, secret: Dict[str, Any]) -> SecretItem:
        meta = secret.get("metadata", {})
        created = parse_rfc3339(meta.get("creationTimestamp"))
        return SecretItem(
            name=meta.get("name", ""),
            secret_id=meta.get("name", ""),
            provider="k8s",
            description=secret.get("type"),
            create_time=created,
            last_changed_date=created,
            labels=dict(meta.get("labels") or {}),
            replication_type="SINGLE_REGION",
            locations=[self.namespace],
        )

    def list_secrets(self) -> List[SecretItem]:
        """List the Secrets of the active namespace."""
        items: List[SecretItem] = []
        token = ""
        while True:
            query = {"limit": PAGE_SIZE}
            if token:
                query["continue"] = token
            page = self._call("GET", self._collection, query=query)
            items.extend(self._item(s) for s in page.get("items", []))
            token = page.get("metadata", {}).get("continue", "")
            if not token:
                break
        items.sort(key=lambda s: s.secret_id.lower())
        return items

    def _get(self, name: str) -> Dict[str, Any]:
        return self._call("GET", f"{self._collection}/{strip_version(name)}")

    def list_versions(self, secret_name: str) -> List[SecretVersionItem]:
        """Kubernetes keeps no history: the only version is the current resourceVersion."""
        secret = self._get(secret_name)
        meta = secret.get("metadata", {})
        version = meta.get("resourceVersion", "")
        return [
            SecretVersionItem(
                version_id=version,
                name=f"{meta.get('name', '')}@{version}",
                state="ENABLED",
                stages=["AWSCURRENT"],
                create_time=parse_rfc3339(meta.get("creationTimestamp")),
            )
        ]

    def access_secret_payload(
        self, secret_name: str, version: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Read the current keys of a Secret as editable text."""
        secret = self._get(secret_name)
        return format_payload(decode_data(secret.get("data") or {})), False

    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        """Create an Opaque Secret, refusing to overwrite an existing one."""
        body = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": secret_id, "namespace": self.namespace, "labels": labels or {}},
            "type": "Opaque",
            "data": encode_data(parse_payload(payload_data)),
        }
        try:
            created = self._call("POST", self._collection, body=body)
        except SecretConflictError as exc:
            raise provider_error(
                CONFLICT,
                _("The secret '{secret}' already exists. Use 'New Version' to modify it.").format(
                    secret=secret_id
                ),
                "k8s",
                exc,
            ) from exc
        return self._item(created)

    def add_secret_version(self, secret_name: str, payload_data: str) -> SecretVersionItem:
        """Replace the keys of a Secret (the type and labels are kept)."""
        current = self._get(secret_name)
        meta = current.get("metadata", {})
        body = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": meta.get("name"),
                "namespace": self.namespace,
                "resourceVersion": meta.get("resourceVersion"),
                "labels": meta.get("labels") or {},
                "annotations": meta.get("annotations") or {},
            },
            "type": current.get("type", "Opaque"),
            "data": encode_data(parse_payload(payload_data)),
        }
        updated = self._call("PUT", f"{self._collection}/{meta.get('name')}", body=body)
        new_meta = updated.get("metadata", {})
        version = new_meta.get("resourceVersion", "")
        return SecretVersionItem(
            version_id=version,
            name=f"{new_meta.get('name', '')}@{version}",
            state="ENABLED",
            stages=["AWSCURRENT"],
        )

    def update_metadata(
        self, secret_name: str, labels: Dict[str, str], description: Optional[str]
    ) -> None:
        """Replace the labels of a Secret, keeping its data and type."""
        current = self._get(secret_name)
        meta = current.get("metadata", {})
        body = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": meta.get("name"),
                "namespace": self.namespace,
                "resourceVersion": meta.get("resourceVersion"),
                "labels": labels,
                "annotations": meta.get("annotations") or {},
            },
            "type": current.get("type", "Opaque"),
            "data": current.get("data") or {},
        }
        self._call("PUT", f"{self._collection}/{meta.get('name')}", body=body)

    def delete_secret(self, secret_name_or_id: str) -> None:
        """Delete a Secret."""
        self._call("DELETE", f"{self._collection}/{strip_version(secret_name_or_id)}")
