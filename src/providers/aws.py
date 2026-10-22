"""Amazon Web Services (AWS) Secrets Manager provider implementation."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import boto3
import botocore.session
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError, ProfileNotFound

from src.providers.base import BaseSecretProvider
from src.exceptions import AuthenticationError, PermissionDeniedError, ProviderError, ResourceNotFoundError
from src.i18n import _
from src.models import SecretItem, SecretVersionItem


COMMON_AWS_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-west-3",
    "eu-central-1",
    "eu-north-1",
    "eu-south-1",
    "sa-east-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
    "ap-northeast-2",
    "ap-south-1",
    "ca-central-1",
    "me-south-1",
    "af-south-1",
]


class AWSSecretClient(BaseSecretProvider):
    """Provider implementation for AWS Secrets Manager."""

    def __init__(
        self,
        profile_name: Optional[str] = None,
        region_name: Optional[str] = None,
    ):
        """Initialize the AWS Secrets Manager client.

        Args:
            profile_name: Optional AWS credentials profile. Defaults to detected active profile.
            region_name: Optional target AWS region code. Defaults to detected active region.
        """
        self._profile_name = profile_name or self.detect_profile()
        self._region_name = region_name or self.detect_region()
        self._session: Optional[boto3.Session] = None
        self._client = None

    @property
    def provider_id(self) -> str:
        """Return the unique provider identifier string ('aws')."""
        return "aws"

    @property
    def provider(self) -> str:
        """Return the provider identifier string (alias for provider_id)."""
        return "aws"

    @property
    def display_name(self) -> str:
        """Return the human-readable provider name shown in the UI switcher."""
        return "Amazon Web Services (AWS)"

    @property
    def icon_name(self) -> str:
        """Return the FreeDesktop symbolic icon name for the context switcher button."""
        return "preferences-system-symbolic"

    @property
    def context_title(self) -> str:
        """Return the localized context title for dialog headers."""
        return _("AWS Profile & Region")

    @property
    def context_subtitle(self) -> str:
        """Return the localized subtitle with active AWS profile and region."""
        return _("AWS: %s (%s)") % (self.profile_name, self.region_name)

    @property
    def context_btn_tooltip(self) -> str:
        """Return the localized tooltip for the profile switcher button."""
        return _("Switch AWS Profile & Region")

    @property
    def loading_message(self) -> str:
        """Return the localized message shown while querying AWS Secrets Manager."""
        return _("Querying AWS Secrets Manager...")

    @property
    def empty_message(self) -> str:
        """Return the localized message shown when no secrets exist in the region."""
        return _("No secrets found in this AWS region.")

    @property
    def error_message(self) -> str:
        """Return the localized message shown when connection or query fails."""
        return _("Could not connect to AWS.")

    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        """Open the modal dialog to configure active AWS credentials profile and region.

        Args:
            parent_window: GTK parent window to transient the dialog for.
            on_success: Callback function invoked after profile/region change.
        """
        from src.ui.dialogs import show_change_aws_context_dialog

        def on_confirm(profile: str, region: str) -> None:
            """Update active AWS profile and region context, invoking completion callback."""
            self.set_context(profile, region)
            on_success()

        show_change_aws_context_dialog(parent_window, self, on_confirm)

    @property
    def profile_name(self) -> str:
        """Return the active AWS credentials profile name."""
        if not self._profile_name:
            self._profile_name = self.detect_profile()
        return self._profile_name

    @profile_name.setter
    def profile_name(self, val: Optional[str]) -> None:
        """Set active AWS credentials profile and invalidate cached session."""
        new_val = val.strip() if val else "default"
        if new_val != self._profile_name:
            self._profile_name = new_val
            self._session = None
            self._client = None

    @property
    def region_name(self) -> str:
        """Return the active AWS region code."""
        if not self._region_name:
            self._region_name = self.detect_region()
        return self._region_name

    @region_name.setter
    def region_name(self, val: Optional[str]) -> None:
        """Set active AWS region code and invalidate cached session."""
        new_val = val.strip() if val else "us-east-1"
        if new_val != self._region_name:
            self._region_name = new_val
            self._session = None
            self._client = None

    def set_context(self, profile: Optional[str], region: Optional[str]) -> None:
        """Update active AWS profile and region simultaneously, resetting client cache.

        Args:
            profile: Optional credentials profile name (defaults to 'default').
            region: Optional target region code (defaults to 'us-east-1').
        """
        self._profile_name = profile.strip() if profile else "default"
        self._region_name = region.strip() if region else "us-east-1"
        self._session = None
        self._client = None

    @classmethod
    def detect_profile(cls) -> str:
        """Detect active AWS credentials profile from environment variables or local configuration.

        Returns:
            str: Detected profile name, defaulting to 'default'.
        """
        for var in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE"):
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        available = cls.list_available_profiles()
        if "default" in available:
            return "default"
        elif available:
            return available[0]
        return "default"

    @classmethod
    def detect_region(cls) -> str:
        """Detect active AWS target region from environment variables, session, or default.

        Returns:
            str: Detected region code, defaulting to 'us-east-1'.
        """
        for var in ("AWS_REGION", "AWS_DEFAULT_REGION"):
            val = os.getenv(var)
            if val and val.strip():
                return val.strip()

        try:
            sess = boto3.Session()
            if sess.region_name:
                return sess.region_name
        except Exception:
            pass

        return "us-east-1"

    @classmethod
    def list_available_profiles(cls) -> List[str]:
        """List all configured AWS profiles available on the system.

        Returns:
            List[str]: Alphabetical list of configured profile names.
        """
        try:
            profiles = botocore.session.Session().available_profiles
            if not profiles:
                return ["default"]
            return sorted(list(set(profiles)))
        except Exception:
            return ["default"]

    @classmethod
    def list_available_regions(cls) -> List[str]:
        """List standard AWS regions supported by Secrets Manager.

        Returns:
            List[str]: List of AWS region code strings.
        """
        try:
            sess = boto3.Session()
            regions = sess.get_available_regions("secretsmanager")
            if regions:
                return sorted(regions)
        except Exception:
            pass
        return COMMON_AWS_REGIONS

    def _get_client(self):
        """Initialize or return cached Boto3 Secrets Manager client instance."""
        if self._client is not None:
            return self._client

        try:
            profile = self.profile_name
            region = self.region_name

            # If profile is 'default' and no explicit credentials file exists, boto3 handles it gracefully
            if profile and profile != "default":
                self._session = boto3.Session(profile_name=profile, region_name=region)
            else:
                self._session = boto3.Session(region_name=region)

            self._client = self._session.client("secretsmanager", region_name=region)
            return self._client
        except ProfileNotFound as exc:
            raise RuntimeError(
                f"El perfil de AWS '{self.profile_name}' no existe en tu archivo ~/.aws/credentials o ~/.aws/config."
            ) from exc
        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "No se encontraron credenciales de AWS activas.\n"
                "Ejecuta en tu terminal:\n"
                "  aws configure\n"
                "o define las variables de entorno AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Error al inicializar cliente de AWS: {exc}") from exc

    def list_secrets(self) -> List[SecretItem]:
        """List all secrets in the current AWS region and profile.

        Returns:
            List[SecretItem]: List of normalized secret item instances.

        Raises:
            AuthenticationError: If AWS credentials are missing or invalid.
            PermissionDeniedError: If caller lacks secretsmanager:ListSecrets permission.
            RuntimeError: If the AWS Secrets Manager request fails.
        """
        client = self._get_client()
        secrets: List[SecretItem] = []

        try:
            paginator = client.get_paginator("list_secrets")
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    name = secret.get("ARN", secret.get("Name", ""))
                    secret_id = secret.get("Name", "")
                    desc = secret.get("Description")
                    created_dt = secret.get("CreatedDate")
                    last_changed = secret.get("LastChangedDate")

                    # Convert AWS tags list [{'Key': 'env', 'Value': 'prod'}] to dict
                    tags_dict: Dict[str, str] = {}
                    for tag in secret.get("Tags", []):
                        k = tag.get("Key")
                        v = tag.get("Value", "")
                        if k:
                            tags_dict[k] = v

                    # Check replication
                    repl_status = secret.get("ReplicationStatus", [])
                    locations = [r.get("Region") for r in repl_status if r.get("Region")]
                    repl_type = "REPLICATED" if locations else "SINGLE_REGION"

                    secrets.append(
                        SecretItem(
                            name=name,
                            secret_id=secret_id,
                            provider="aws",
                            description=desc,
                            create_time=created_dt,
                            last_changed_date=last_changed,
                            labels=tags_dict,
                            replication_type=repl_type,
                            locations=locations,
                            kms_key_id=secret.get("KmsKeyId"),
                        )
                    )

            secrets.sort(key=lambda s: s.secret_id.lower())
            return secrets

        except (NoCredentialsError, PartialCredentialsError) as exc:
            raise RuntimeError(
                "No se encontraron credenciales de AWS válidas.\n"
                "Ejecuta 'aws configure' o verifica tus variables de entorno."
            ) from exc
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    f"Permiso denegado para AWS Secrets Manager en la región '{self.region_name}'.\n"
                    f"Detalle: {error_msg}"
                ) from exc
            raise RuntimeError(f"Error en AWS Secrets Manager: {error_msg}") from exc

    def list_versions(self, secret_id_or_arn: str) -> List[SecretVersionItem]:
        """List all versions and staging labels of an AWS secret.

        Args:
            secret_id_or_arn: AWS Secret Name or ARN.

        Returns:
            List[SecretVersionItem]: Chronologically ordered versions with staging labels.

        Raises:
            ResourceNotFoundError: If the secret does not exist.
            PermissionDeniedError: If caller lacks DescribeSecret permission.
            RuntimeError: If operation fails.
        """
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
                    vid = v.get("VersionId", "")
                    stages = v.get("VersionStages", [])
                    created_dt = v.get("CreatedDate")
                    state_str = stages[0] if stages else "DEPRECATED"

                    versions.append(
                        SecretVersionItem(
                            version_id=vid,
                            name=f"{actual_secret_id}@{vid}",
                            state=state_str,
                            stages=stages,
                            create_time=created_dt,
                            destroy_time=None,
                        )
                    )

                next_token = resp.get("NextToken")
                if not next_token:
                    break

            # Sort: AWSCURRENT first, then by create_time descending
            def sort_key(ver: SecretVersionItem):
                """Generate sorting tuple prioritizing AWSCURRENT before create_time."""
                is_current = 1 if "AWSCURRENT" in ver.stages else 0
                ts = ver.create_time.timestamp() if ver.create_time else 0
                return (is_current, ts)

            versions.sort(key=sort_key, reverse=True)
            return versions

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(f"Permiso denegado al listar versiones: {error_msg}") from exc
            raise RuntimeError(f"Error al listar versiones del secreto: {error_msg}") from exc

    def access_secret_payload(
        self,
        secret_id_or_arn: str,
        version_id: Optional[str] = None,
        version_stage: Optional[str] = None,
    ) -> Tuple[str, bool]:
        """Fetch the secret value (SecretString or SecretBinary).

        Args:
            secret_id_or_arn: AWS Secret Name or ARN.
            version_id: Optional unique version UUID.
            version_stage: Optional staging label (e.g. 'AWSCURRENT').

        Returns:
            Tuple[str, bool]: Decoded string value and is_binary boolean flag.

        Raises:
            FileNotFoundError: If the secret or version does not exist.
            PermissionError: If caller lacks secretsmanager:GetSecretValue permission.
            RuntimeError: If access fails.
        """
        client = self._get_client()

        # Handle secret_id_or_arn if passed with '@version_id' format
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
                return f"[Datos binarios - {len(binary_data)} bytes]\n\n{hex_str}", True
            return "", False

        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            error_msg = exc.response.get("Error", {}).get("Message", str(exc))
            if error_code in ("AccessDeniedException", "UnauthorizedException"):
                raise PermissionError(
                    f"Permiso denegado para acceder al valor del secreto '{actual_secret_id}'.\n"
                    f"Detalle: {error_msg}"
                ) from exc
            elif error_code == "ResourceNotFoundException":
                raise FileNotFoundError(f"El secreto o versión '{actual_secret_id}' no fue encontrado.") from exc
            raise RuntimeError(f"Error al obtener el valor del secreto: {error_msg}") from exc

    def create_secret(
        self,
        secret_id: str,
        payload_data: Optional[str] = None,
        description: Optional[str] = None,
        labels: Optional[dict] = None,
        kms_key_id: Optional[str] = None,
    ) -> SecretItem:
        """Create a new secret in AWS Secrets Manager.

        Args:
            secret_id: Human-readable secret identifier.
            payload_data: Initial secret string payload.
            description: Optional human-readable description.
            labels: Optional dictionary of tags.
            kms_key_id: Optional KMS encryption key ID or ARN.

        Returns:
            SecretItem: Newly created secret item metadata.

        Raises:
            ValueError: If secret identifier already exists.
            PermissionError: If caller lacks CreateSecret permissions.
            RuntimeError: If creation fails.
        """
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
                raise PermissionError(f"Permiso denegado para crear el secreto: {error_msg}") from exc
            raise RuntimeError(f"Error al crear el secreto en AWS: {error_msg}") from exc

    def add_secret_version(self, secret_id_or_arn: str, payload_data: str) -> SecretVersionItem:
        """Add a new version payload to an existing AWS secret.

        Args:
            secret_id_or_arn: Secret Name or ARN.
            payload_data: String payload content for the new version.

        Returns:
            SecretVersionItem: Newly created secret version item.

        Raises:
            PermissionError: If caller lacks PutSecretValue permission.
            RuntimeError: If operation fails.
        """
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
                raise PermissionError(f"Permiso denegado para actualizar el secreto: {error_msg}") from exc
            raise RuntimeError(f"Error al añadir versión en AWS: {error_msg}") from exc

    def delete_secret(
        self,
        secret_id_or_arn: str,
        force: bool = True,
        recovery_days: int = 7,
    ) -> None:
        """Delete a secret in AWS Secrets Manager.

        Args:
            secret_id_or_arn: AWS Secret Name or ARN to delete.
            force: If True, deletes immediately without recovery window.
            recovery_days: Recovery window in days if force is False.

        Raises:
            PermissionError: If caller lacks DeleteSecret permission.
            RuntimeError: If deletion fails.
        """
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
                raise PermissionError(f"Permiso denegado para eliminar el secreto: {error_msg}") from exc
            raise RuntimeError(f"Error al eliminar el secreto en AWS: {error_msg}") from exc
