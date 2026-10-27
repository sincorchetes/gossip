"""CRUD operations mixin for Amazon Web Services (AWS) Secrets Manager."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
    ProfileNotFound,
    ReadTimeoutError,
)

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers.aws.helpers import parse_aws_secret_item, parse_aws_version_item
from src.providers.errors import (
    CONNECT_TIMEOUT,
    OTHER,
    READ_TIMEOUT,
    RETRIES,
    client_failure,
    guard_network,
    provider_error,
)

BINARY_PREFIX = "base64:"
_CLIENT_CONFIG = Config(
    connect_timeout=CONNECT_TIMEOUT,
    read_timeout=READ_TIMEOUT,
    retries={"max_attempts": RETRIES, "mode": "standard"},
)
NETWORK_ERRORS = (
    ConnectTimeoutError,
    ReadTimeoutError,
    EndpointConnectionError,
    ConnectionClosedError,
)
AWS_METHODS = (
    "update_metadata",
    "list_secrets",
    "list_versions",
    "access_secret_payload",
    "create_secret",
    "add_secret_version",
    "delete_secret",
)


class AWSConnectionMixin:
    """Creates the boto3 client for the configured profile, region and service."""

    profile_name: str
    region_name: str
    _client: Any
    _session: Any
    _service_name = "secretsmanager"

    def _get_client(self) -> Any:
        """Initialize or return cached Boto3 Secrets Manager client instance."""
        if self._client is not None:
            return self._client

        try:
            profile = self.profile_name
            region = self.region_name

            if profile and profile != "default":
                self._session = boto3.Session(profile_name=profile, region_name=region)
            else:
                self._session = boto3.Session(region_name=region)

            self._client = self._session.client(
                self._service_name, region_name=region, config=_CLIENT_CONFIG
            )
            return self._client
        except ProfileNotFound as exc:
            raise provider_error(
                OTHER,
                _(
                    "The AWS profile '{profile}' does not exist in your ~/.aws/credentials or ~/.aws/config file."
                ).format(profile=self.profile_name),
                "aws",
                exc,
            ) from exc
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise provider_error(
                OTHER,
                _(
                    "No active AWS credentials found.\n"
                    "Run in your terminal:\n"
                    "  aws configure\n"
                    "or set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
                ),
                "aws",
                exc,
            ) from exc
        except Exception as exc:
            raise provider_error(
                OTHER, f"{_('Error initializing AWS client')}: {exc}", "aws", exc
            ) from exc


@guard_network("aws", "AWS", NETWORK_ERRORS, *AWS_METHODS)
class AWSOperationsMixin(AWSConnectionMixin):
    """Secret listing, CRUD and payload access for AWS Secrets Manager."""

    def list_secrets(self) -> List[SecretItem]:
        """List all secrets in the current AWS region and profile."""
        client = self._get_client()
        secrets: List[SecretItem] = []

        try:
            paginator = client.get_paginator("list_secrets")
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    secrets.append(parse_aws_secret_item(secret))

            secrets.sort(key=lambda s: s.secret_id.lower())
            return secrets

        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise provider_error(
                OTHER,
                _(
                    "No valid AWS credentials found.\n"
                    "Run 'aws configure' or verify your environment variables."
                ),
                "aws",
                exc,
            ) from exc
        except ClientError as exc:
            raise client_failure(
                exc,
                "aws",
                denied=lambda detail: _(
                    "Permission denied for AWS Secrets Manager in region '{region}'.\n"
                    "Detail: {detail}"
                ).format(region=self.region_name, detail=detail),
                other=_("AWS Secrets Manager error"),
            ) from exc

    def list_versions(self, secret_id_or_arn: str) -> List[SecretVersionItem]:
        """List all versions and staging labels of an AWS secret."""
        client = self._get_client()
        versions: List[SecretVersionItem] = []
        actual_secret_id = secret_id_or_arn.split("@")[0]

        try:
            next_token = None
            while True:
                params = {
                    "SecretId": actual_secret_id,
                    "IncludeDeprecated": True,
                }
                if next_token:
                    params["NextToken"] = next_token

                resp = client.list_secret_version_ids(**params)
                for v in resp.get("Versions", []):
                    versions.append(parse_aws_version_item(v, actual_secret_id))

                next_token = resp.get("NextToken")
                if not next_token:
                    break

            def sort_key(ver: SecretVersionItem):
                is_current = 1 if "AWSCURRENT" in ver.stages else 0
                ts = ver.create_time.timestamp() if ver.create_time else 0
                return (is_current, ts)

            versions.sort(key=sort_key, reverse=True)
            return versions

        except ClientError as exc:
            raise client_failure(
                exc,
                "aws",
                denied=_("Permission denied while listing versions"),
                other=_("Error listing secret versions"),
            ) from exc

    def access_secret_payload(
        self,
        secret_id_or_arn: str,
        version_id: Optional[str] = None,
        version_stage: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """Fetch the secret value (SecretString or SecretBinary)."""
        client = self._get_client()

        actual_secret_id = secret_id_or_arn
        if "@" in secret_id_or_arn:
            parts = secret_id_or_arn.split("@", 1)
            actual_secret_id = parts[0]
            if not version_id:
                version_id = parts[1]

        params = {"SecretId": actual_secret_id}
        if version_id:
            params["VersionId"] = version_id
        elif version_stage:
            params["VersionStage"] = version_stage

        try:
            resp = client.get_secret_value(**params)
            if "SecretString" in resp:
                return resp["SecretString"], False
            elif "SecretBinary" in resp:
                return BINARY_PREFIX + base64.b64encode(resp["SecretBinary"]).decode("ascii"), True
            return "", False

        except ClientError as exc:
            raise client_failure(
                exc,
                "aws",
                denied=lambda detail: _(
                    "Permission denied to read secret value for '{secret}' in region '{region}'.\n"
                    "Detail: {detail}"
                ).format(secret=actual_secret_id, region=self.region_name, detail=detail),
                missing=_("The secret or version '{secret}' was not found.").format(
                    secret=actual_secret_id
                ),
                other=_("Error retrieving secret value"),
            ) from exc

    def create_secret(
        self,
        secret_id: str,
        payload_data: Optional[str] = None,
        labels: Optional[dict] = None,
        description: Optional[str] = None,
        kms_key_id: Optional[str] = None,
    ) -> SecretItem:
        """Create a new secret in AWS Secrets Manager."""
        client = self._get_client()

        params: Dict[str, Any] = {
            "Name": secret_id,
        }
        if description:
            params["Description"] = description
        if payload_data is not None:
            params["SecretString"] = payload_data
        if kms_key_id:
            params["KmsKeyId"] = kms_key_id

        if labels:
            tags_list = [{"Key": k, "Value": str(v)} for k, v in labels.items()]
            params["Tags"] = tags_list

        try:
            resp = client.create_secret(**params)
            arn = resp.get("ARN", secret_id)

            return SecretItem(
                name=arn,
                secret_id=secret_id,
                provider="aws",
                description=description,
                create_time=datetime.now(),
                labels=labels or {},
                replication_type="SINGLE_REGION",
                locations=[],
            )
        except ClientError as exc:
            raise client_failure(
                exc,
                "aws",
                denied=_("Permission denied to create secret"),
                other=_("Error creating secret in AWS"),
                conflict=_(
                    "The secret '{secret}' already exists. Use 'New Version' to modify it."
                ).format(secret=secret_id),
            ) from exc

    def _value_params(self, client: Any, secret_id: str, payload: str) -> dict:
        """Choose SecretBinary or SecretString for a new version.

        Binary secrets are shown as ``base64:<data>``; the text is converted back to bytes only
        when the secret currently holds binary data, so text secrets that merely start with
        ``base64:`` are never reinterpreted.
        """
        if payload.startswith(BINARY_PREFIX):
            current = client.get_secret_value(SecretId=secret_id)
            if "SecretBinary" in current:
                try:
                    return {
                        "SecretBinary": base64.b64decode(
                            payload[len(BINARY_PREFIX) :], validate=True
                        )
                    }
                except binascii.Error as exc:
                    raise ValueError(
                        _("The value starts with 'base64:' but is not valid base64.")
                    ) from exc
        return {"SecretString": payload}

    def update_metadata(
        self, secret_name: str, labels: Dict[str, str], description: Optional[str]
    ) -> None:
        """Replace the tags and set the description of a secret."""
        client = self._get_client()
        secret_id = secret_name.split("@")[0]
        try:
            if description is not None:
                client.update_secret(SecretId=secret_id, Description=description)
            current = {
                t["Key"]: t.get("Value", "")
                for t in client.describe_secret(SecretId=secret_id).get("Tags", [])
            }
            removed = [key for key in current if key not in labels]
            changed = [
                {"Key": k, "Value": str(v)} for k, v in labels.items() if current.get(k) != str(v)
            ]
            if removed:
                client.untag_resource(SecretId=secret_id, TagKeys=removed)
            if changed:
                client.tag_resource(SecretId=secret_id, Tags=changed)
        except ClientError as exc:
            raise client_failure(
                exc,
                "aws",
                denied=_("Permission denied to edit the secret"),
                other=_("Error editing secret"),
            ) from exc

    def add_secret_version(self, secret_id_or_arn: str, payload_data: str) -> SecretVersionItem:
        """Add a new version payload to an existing AWS secret."""
        client = self._get_client()
        actual_secret_id = secret_id_or_arn.split("@")[0]

        try:
            value_params = self._value_params(client, actual_secret_id, payload_data)
            resp = client.put_secret_value(SecretId=actual_secret_id, **value_params)
            vid = resp.get("VersionId", "")
            stages = resp.get("VersionStages", ["AWSCURRENT"])

            return SecretVersionItem(
                version_id=vid,
                name=f"{actual_secret_id}@{vid}",
                state="AWSCURRENT",
                stages=stages,
                create_time=datetime.now(),
                destroy_time=None,
            )
        except ClientError as exc:
            raise client_failure(
                exc,
                "aws",
                denied=_("Permission denied to update secret"),
                other=_("Error adding version in AWS"),
            ) from exc

    def delete_secret(
        self,
        secret_id_or_arn: str,
        force: bool = False,
        recovery_days: int = 7,
    ) -> None:
        """Delete a secret in AWS Secrets Manager.

        By default the secret is only scheduled for deletion and can be restored during the
        recovery window; ``force`` deletes it immediately and irrecoverably.
        """
        client = self._get_client()
        actual_secret_id = secret_id_or_arn.split("@")[0]

        params: Dict[str, Any] = {"SecretId": actual_secret_id}
        if force:
            params["ForceDeleteWithoutRecovery"] = True
        else:
            params["RecoveryWindowInDays"] = recovery_days

        try:
            client.delete_secret(**params)
        except ClientError as exc:
            raise client_failure(
                exc,
                "aws",
                denied=_("Permission denied to delete secret"),
                other=_("Error deleting secret in AWS"),
            ) from exc
