"""CRUD operations mixin for Amazon Web Services (AWS) Secrets Manager."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional, Tuple

import boto3
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
    PartialCredentialsError,
    ProfileNotFound,
)

from src.i18n import _
from src.models import SecretItem, SecretVersionItem
from src.providers.aws_helpers import parse_aws_secret_item, parse_aws_version_item


class AWSOperationsMixin:
    """Provides client initialization, secret listing, CRUD, and payload access for AWS."""

    profile_name: str
    region_name: str
    _client: Any
    _session: Any

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

            self._client = self._session.client("secretsmanager", region_name=region)
            return self._client
        except ProfileNotFound as exc:
            raise RuntimeError(
                _(
                    "The AWS profile '{profile}' does not exist in your ~/.aws/credentials or ~/.aws/config file."
                ).format(profile=self.profile_name)
            ) from exc
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                _(
                    "No active AWS credentials found.\n"
                    "Run in your terminal:\n"
                    "  aws configure\n"
                    "or set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
                )
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"{_('Error initializing AWS client')}: {exc}") from exc

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
            raise RuntimeError(
                _(
                    "No valid AWS credentials found.\n"
                    "Run 'aws configure' or verify your environment variables."
                )
            ) from exc
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    _(
                        "Permission denied for AWS Secrets Manager in region '{region}'.\n"
                        "Detail: {detail}"
                    ).format(region=self.region_name, detail=error_msg)
                ) from exc
            raise RuntimeError(f"{_('AWS Secrets Manager error')}: {error_msg}") from exc

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
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    f"{_('Permission denied while listing versions')}: {error_msg}"
                ) from exc
            raise RuntimeError(f"{_('Error listing secret versions')}: {error_msg}") from exc

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
                binary_data = resp["SecretBinary"]
                hex_str = binary_data.hex(" ")
                return f"[{_('Binary data')} - {len(binary_data)} bytes]\n\n{hex_str}", True
            return "", False

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    _(
                        "Permission denied to read secret value for '{secret}' in region '{region}'.\n"
                        "Detail: {detail}"
                    ).format(secret=actual_secret_id, region=self.region_name, detail=error_msg)
                ) from exc
            elif error_code == "ResourceNotFoundException":
                raise FileNotFoundError(
                    _("The secret or version '{secret}' was not found.").format(
                        secret=actual_secret_id
                    )
                ) from exc
            raise RuntimeError(f"{_('Error retrieving secret value')}: {error_msg}") from exc

    def create_secret(
        self,
        secret_id: str,
        payload_data: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[dict] = None,
        kms_key_id: Optional[str] = None,
    ) -> SecretItem:
        """Create a new secret in AWS Secrets Manager."""
        client = self._get_client()

        params = {
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
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    f"{_('Permission denied to create secret')}: {error_msg}"
                ) from exc
            raise RuntimeError(f"{_('Error creating secret in AWS')}: {error_msg}") from exc

    def add_secret_version(self, secret_id_or_arn: str, payload_data: str) -> SecretVersionItem:
        """Add a new version payload to an existing AWS secret."""
        client = self._get_client()
        actual_secret_id = secret_id_or_arn.split("@")[0]

        try:
            resp = client.put_secret_value(
                SecretId=actual_secret_id,
                SecretString=payload_data,
            )
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
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    f"{_('Permission denied to update secret')}: {error_msg}"
                ) from exc
            raise RuntimeError(f"{_('Error adding version in AWS')}: {error_msg}") from exc

    def delete_secret(
        self,
        secret_id_or_arn: str,
        force: bool = True,
        recovery_days: int = 7,
    ) -> None:
        """Delete a secret in AWS Secrets Manager."""
        client = self._get_client()
        actual_secret_id = secret_id_or_arn.split("@")[0]

        params = {"SecretId": actual_secret_id}
        if force:
            params["ForceDeleteWithoutRecovery"] = True
        else:
            params["RecoveryWindowInDays"] = recovery_days

        try:
            client.delete_secret(**params)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    f"{_('Permission denied to delete secret')}: {error_msg}"
                ) from exc
            raise RuntimeError(f"{_('Error deleting secret in AWS')}: {error_msg}") from exc
