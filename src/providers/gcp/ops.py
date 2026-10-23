"""CRUD operations mixin for Google Cloud Platform Secret Manager provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from google.api_core.exceptions import GoogleAPICallError, NotFound, PermissionDenied
from google.cloud import secretmanager_v1

from src.exceptions import (
    PermissionDeniedError,
    ProviderError,
    ResourceNotFoundError,
)
from src.i18n import _
from src.models import GCPProjectItem, SecretItem, SecretVersionItem
from src.providers.gcp.discovery import fetch_available_projects
from src.providers.gcp.helpers import parse_secret_item, parse_version_item

if TYPE_CHECKING:
    from google.auth.credentials import Credentials


class GCPOperationsMixin:
    """Provides secret listing, versioning, CRUD, and payload access for GCP Secret Manager."""

    project_id: Optional[str]
    _credentials: Optional[Credentials]

    def initialize_client(self) -> secretmanager_v1.SecretManagerServiceClient: ...

    def list_secrets(self, project_id: Optional[str] = None) -> List[SecretItem]:
        """List all secrets in the given or active GCP project."""
        client = self.initialize_client()
        active_project = project_id or self.project_id
        if not active_project:
            raise ValueError(_("No GCP project ID specified."))

        parent = f"projects/{active_project}"
        try:
            request = secretmanager_v1.ListSecretsRequest(parent=parent)
            page_result = client.list_secrets(request=request)
            secrets = [parse_secret_item(secret) for secret in page_result]
            secrets.sort(key=lambda s: s.secret_id.lower())
            return secrets
        except PermissionDenied as exc:
            raise PermissionDeniedError(
                _(
                    "Permission denied for GCP Secret Manager in project '{project}'.\n"
                    "Verify that your account has the 'Secret Manager Secret Accessor' or 'Secret Manager Admin' role."
                ).format(project=active_project),
                provider="gcp",
                original_error=exc,
            ) from exc
        except NotFound as exc:
            raise ResourceNotFoundError(
                _("The GCP project '{project}' was not found.").format(project=active_project),
                provider="gcp",
                original_error=exc,
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(
                f"{_('GCP Secret Manager API error')}: {exc.message}",
                provider="gcp",
                original_error=exc,
            ) from exc

    def list_versions(self, secret_full_name: str) -> List[SecretVersionItem]:
        """Lists all versions of a specific secret."""
        client = self.initialize_client()
        parent = secret_full_name
        if not parent.startswith("projects/"):
            parent = f"projects/{self.project_id}/secrets/{secret_full_name}"

        try:
            request = secretmanager_v1.ListSecretVersionsRequest(parent=parent)
            page_result = client.list_secret_versions(request=request)
            versions = [parse_version_item(version) for version in page_result]

            def parse_ver_id(ver: SecretVersionItem) -> int:
                try:
                    return int(ver.version_id)
                except ValueError:
                    return 0

            versions.sort(key=parse_ver_id, reverse=True)
            return versions
        except PermissionDenied as exc:
            raise PermissionDeniedError(
                _("Permission denied while listing secret versions."),
                provider="gcp",
                original_error=exc,
            ) from exc
        except NotFound as exc:
            raise ResourceNotFoundError(
                _("The secret '{secret}' does not exist.").format(secret=secret_full_name),
                provider="gcp",
                original_error=exc,
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(
                f"{_('Error fetching secret versions')}: {exc.message}",
                provider="gcp",
                original_error=exc,
            ) from exc

    def access_secret_payload(self, version_full_name: str) -> Tuple[str, bool]:
        """Fetch the payload of a specific secret version."""
        client = self.initialize_client()
        name = version_full_name
        if not name.startswith("projects/"):
            name = f"projects/{self.project_id}/secrets/{version_full_name}/versions/latest"
        elif "/versions/" not in name:
            name = f"{name}/versions/latest"

        request = secretmanager_v1.AccessSecretVersionRequest(name=name)

        try:
            response = client.access_secret_version(request=request)
            payload_bytes = response.payload.data

            try:
                decoded_str = payload_bytes.decode("utf-8")
                return decoded_str, False
            except UnicodeDecodeError:
                hex_str = payload_bytes.hex(" ")
                return f"[{_('Binary data')} - {len(payload_bytes)} bytes]\n\n{hex_str}", True

        except PermissionDenied as exc:
            raise PermissionDeniedError(
                _(
                    "Permission denied while accessing secret payload.\n"
                    "Requires 'roles/secretmanager.secretAccessor' role."
                ),
                provider="gcp",
                original_error=exc,
            ) from exc
        except NotFound as exc:
            raise ResourceNotFoundError(
                _("The secret or version '{version}' does not exist.").format(
                    version=version_full_name
                ),
                provider="gcp",
                original_error=exc,
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(
                f"{_('Error accessing secret')}: {exc.message}", provider="gcp", original_error=exc
            ) from exc

    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SecretItem:
        """Creates a new secret and adds its first version."""
        client = self.initialize_client()
        active_project = project_id or self.project_id
        if not active_project:
            raise ValueError(_("No GCP project ID configured."))

        parent = f"projects/{active_project}"
        try:
            secret = client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": {
                        "replication": {"automatic": {}},
                        "labels": labels or {},
                    },
                }
            )

            if payload_data is not None:
                client.add_secret_version(
                    request={
                        "parent": secret.name,
                        "payload": {"data": payload_data.encode("utf-8")},
                    }
                )

            return parse_secret_item(secret)
        except PermissionDenied as exc:
            raise PermissionError(
                _("Permission denied to create secret.\nRequires 'roles/secretmanager.admin' role.")
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(
                f"{_('Error creating secret')}: {exc.message}",
                provider="gcp",
                original_error=exc,
            ) from exc

    def add_secret_version(self, secret_name_or_id: str, payload_data: str) -> SecretVersionItem:
        """Appends a new version to an existing secret."""
        client = self.initialize_client()
        parent = secret_name_or_id
        if not parent.startswith("projects/"):
            parent = f"projects/{self.project_id}/secrets/{secret_name_or_id}"

        try:
            version = client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": payload_data.encode("utf-8")},
                }
            )
            return parse_version_item(version)
        except PermissionDenied as exc:
            raise PermissionError(
                _("Permission denied to add version.\nRequires 'roles/secretmanager.admin' role.")
            ) from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"{_('Error adding version')}: {exc.message}") from exc

    def enable_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Enables a previously disabled secret version."""
        client = self.initialize_client()
        try:
            version = client.enable_secret_version(request={"name": version_full_name})
            return parse_version_item(version)
        except PermissionDenied as exc:
            raise PermissionError(_("Permission denied to enable version.")) from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"{_('Error enabling version')}: {exc.message}") from exc

    def disable_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Disables a secret version so its payload cannot be accessed."""
        client = self.initialize_client()
        try:
            version = client.disable_secret_version(request={"name": version_full_name})
            return parse_version_item(version)
        except PermissionDenied as exc:
            raise PermissionError(_("Permission denied to disable version.")) from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"{_('Error disabling version')}: {exc.message}") from exc

    def destroy_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Irreversibly destroys the payload of a secret version."""
        client = self.initialize_client()
        try:
            version = client.destroy_secret_version(request={"name": version_full_name})
            return parse_version_item(version)
        except PermissionDenied as exc:
            raise PermissionError(_("Permission denied to destroy version.")) from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"{_('Error destroying version')}: {exc.message}") from exc

    def delete_secret(self, secret_name_or_id: str) -> None:
        """Permanently deletes a secret and all its versions."""
        client = self.initialize_client()
        full_name = secret_name_or_id
        if not full_name.startswith("projects/"):
            full_name = f"projects/{self.project_id}/secrets/{secret_name_or_id}"
        try:
            client.delete_secret(request={"name": full_name})
        except PermissionDenied as exc:
            raise PermissionDeniedError(
                _(
                    "Permission denied to delete secret.\n"
                    "Requires 'roles/secretmanager.admin' role."
                ),
                provider="gcp",
                original_error=exc,
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(
                f"{_('Error deleting secret')}: {exc.message}", provider="gcp", original_error=exc
            ) from exc

    def list_available_projects(self) -> List[GCPProjectItem]:
        """Lists active GCP projects accessible to the authenticated credentials."""
        self.initialize_client()
        return fetch_available_projects(self._credentials)
