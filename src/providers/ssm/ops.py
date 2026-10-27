"""Parameter Store operations for the AWS Systems Manager provider."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from botocore.exceptions import ClientError

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers.aws.ops import AWS_METHODS, NETWORK_ERRORS, AWSConnectionMixin
from src.providers.common import split_numeric_version
from src.providers.errors import CONFLICT, client_failure, guard_network, provider_error

_DENIED = ("AccessDeniedException", "UnauthorizedException")
_NOT_FOUND = ("ParameterNotFound", "ParameterVersionNotFound")
DEFAULT_TYPE = "SecureString"


def _parameter_item(info: Dict[str, Any]) -> SecretItem:
    """Convert a describe_parameters entry into a SecretItem."""
    labels = {"type": info.get("Type", "")}
    if info.get("Tier"):
        labels["tier"] = info["Tier"]
    return SecretItem(
        name=info["Name"],
        secret_id=info["Name"],
        provider="ssm",
        description=info.get("Description"),
        create_time=info.get("LastModifiedDate"),
        last_changed_date=info.get("LastModifiedDate"),
        labels=labels,
        replication_type="SINGLE_REGION",
        kms_key_id=info.get("KeyId"),
    )


@guard_network("ssm", "AWS Parameter Store", NETWORK_ERRORS, *AWS_METHODS, "load_metadata")
class SSMOperationsMixin(AWSConnectionMixin):
    """Listing, history and CRUD over AWS Systems Manager Parameter Store."""

    _service_name = "ssm"

    def _translate(self, exc: ClientError, subject: str) -> Exception:
        """Map a botocore error to the domain exceptions."""
        return client_failure(
            exc,
            "ssm",
            denied=lambda detail: _(
                "Permission denied for Parameter Store in region '{region}'.\nDetail: {detail}"
            ).format(region=self.region_name, detail=detail),
            missing=_("The parameter or version '{name}' was not found.").format(name=subject),
            other=lambda detail: _("Parameter Store error: {detail}").format(detail=detail),
            denied_codes=_DENIED,
            missing_codes=_NOT_FOUND,
        )

    def list_secrets(self) -> List[SecretItem]:
        """List every parameter of the region."""
        client = self._get_client()
        items: List[SecretItem] = []
        try:
            for page in client.get_paginator("describe_parameters").paginate():
                items.extend(_parameter_item(p) for p in page.get("Parameters", []))
        except ClientError as exc:
            raise self._translate(exc, "") from exc
        items.sort(key=lambda s: s.secret_id.lower())
        return items

    def list_versions(self, secret_name: str) -> List[SecretVersionItem]:
        """List the history of a parameter, newest first; labels are shown as stages."""
        client = self._get_client()
        name, _version = split_numeric_version(secret_name)
        history: List[Dict[str, Any]] = []
        try:
            paginator = client.get_paginator("get_parameter_history")
            for page in paginator.paginate(Name=name, WithDecryption=False):
                history.extend(page.get("Parameters", []))
        except ClientError as exc:
            raise self._translate(exc, name) from exc
        history.sort(key=lambda p: int(p.get("Version", 0)), reverse=True)
        latest = history[0].get("Version") if history else None
        versions = []
        for entry in history:
            number = str(entry.get("Version", ""))
            stages = list(entry.get("Labels", []))
            if entry.get("Version") == latest:
                stages.insert(0, "AWSCURRENT")
            versions.append(
                SecretVersionItem(
                    version_id=number,
                    name=f"{name}@{number}",
                    state="ENABLED",
                    stages=stages,
                    create_time=entry.get("LastModifiedDate"),
                )
            )
        return versions

    def access_secret_payload(
        self, secret_name: str, version: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Read a parameter (a specific version when given), decrypting SecureStrings."""
        client = self._get_client()
        name, number = split_numeric_version(secret_name, version)
        selector = f"{name}:{number}" if number else name
        try:
            resp = client.get_parameter(Name=selector, WithDecryption=True)
        except ClientError as exc:
            raise self._translate(exc, selector) from exc
        return resp["Parameter"]["Value"], False

    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        """Create a SecureString parameter, refusing to overwrite an existing one."""
        client = self._get_client()
        params: Dict[str, Any] = {
            "Name": secret_id,
            "Value": payload_data,
            "Type": DEFAULT_TYPE,
            "Overwrite": False,
        }
        if description:
            params["Description"] = description
        if labels:
            params["Tags"] = [{"Key": k, "Value": str(v)} for k, v in labels.items()]
        try:
            client.put_parameter(**params)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ParameterAlreadyExists":
                raise provider_error(
                    CONFLICT,
                    _(
                        "The parameter '{name}' already exists. Use 'New Version' to modify it."
                    ).format(name=secret_id),
                    "ssm",
                    exc,
                ) from exc
            raise self._translate(exc, secret_id) from exc
        return SecretItem(
            name=secret_id,
            secret_id=secret_id,
            provider="ssm",
            description=description,
            labels={"type": DEFAULT_TYPE, **(labels or {})},
            replication_type="SINGLE_REGION",
        )

    def add_secret_version(self, secret_name: str, payload_data: str) -> SecretVersionItem:
        """Overwrite a parameter, which creates a new version (the type is kept)."""
        client = self._get_client()
        name, _version = split_numeric_version(secret_name)
        try:
            current = client.get_parameter(Name=name, WithDecryption=False)["Parameter"]
            resp = client.put_parameter(
                Name=name,
                Value=payload_data,
                Type=current.get("Type", DEFAULT_TYPE),
                Overwrite=True,
            )
        except ClientError as exc:
            raise self._translate(exc, name) from exc
        number = str(resp.get("Version", ""))
        return SecretVersionItem(
            version_id=number, name=f"{name}@{number}", state="ENABLED", stages=["AWSCURRENT"]
        )

    def load_metadata(self, secret: SecretItem) -> Tuple[Dict[str, str], Optional[str]]:
        """Read the tags of a parameter (the listing does not include them)."""
        client = self._get_client()
        try:
            tags = client.list_tags_for_resource(ResourceType="Parameter", ResourceId=secret.name)
        except ClientError as exc:
            raise self._translate(exc, secret.name) from exc
        return {t["Key"]: t.get("Value", "") for t in tags.get("TagList", [])}, secret.description

    def update_metadata(
        self, secret_name: str, labels: Dict[str, str], description: Optional[str]
    ) -> None:
        """Replace the tags of a parameter (changing a description would create a version)."""
        client = self._get_client()
        name, _version = split_numeric_version(secret_name)
        try:
            current = {
                t["Key"]: t.get("Value", "")
                for t in client.list_tags_for_resource(
                    ResourceType="Parameter", ResourceId=name
                ).get("TagList", [])
            }
            removed = [key for key in current if key not in labels]
            changed = [
                {"Key": k, "Value": str(v)} for k, v in labels.items() if current.get(k) != str(v)
            ]
            if removed:
                client.remove_tags_from_resource(
                    ResourceType="Parameter", ResourceId=name, TagKeys=removed
                )
            if changed:
                client.add_tags_to_resource(ResourceType="Parameter", ResourceId=name, Tags=changed)
        except ClientError as exc:
            raise self._translate(exc, name) from exc

    def delete_secret(self, secret_name_or_id: str, **_kwargs: Any) -> None:
        """Delete a parameter with its whole history."""
        client = self._get_client()
        name, _version = split_numeric_version(secret_name_or_id)
        try:
            client.delete_parameter(Name=name)
        except ClientError as exc:
            raise self._translate(exc, name) from exc
