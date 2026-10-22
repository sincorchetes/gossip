"""Google Cloud Platform Secret Manager provider implementation."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import google.auth
from google.api_core.exceptions import GoogleAPICallError, NotFound, PermissionDenied
from google.auth.exceptions import DefaultCredentialsError, GoogleAuthError
from google.cloud import secretmanager_v1

from src.providers.base import BaseSecretProvider
from src.exceptions import AuthenticationError, PermissionDeniedError, ProviderError, ResourceNotFoundError
from src.i18n import _
from src.models import GCPProjectItem, SecretItem, SecretVersionItem


def _parse_timestamp(ts: Any) -> Optional[datetime]:
    """Safely convert GCP timestamps to standard Python datetime instances.

    Args:
        ts: Raw timestamp object (DatetimeWithNanoseconds, protobuf Timestamp, or datetime).

    Returns:
        Optional[datetime]: Converted datetime instance or None if input was None.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if hasattr(ts, "ToDatetime"):
        return ts.ToDatetime()
    if hasattr(ts, "to_datetime"):
        return ts.to_datetime()
    return None


class GCPSecretClient(BaseSecretProvider):
    """Provider implementation for Google Cloud Platform Secret Manager."""

    def __init__(self, project_id: Optional[str] = None):
        """Initialize the GCP Secret Manager client.

        Args:
            project_id: Optional GCP project ID. If omitted, attempts autodetection.
        """
        self._project_id = project_id
        self._client: Optional[secretmanager_v1.SecretManagerServiceClient] = None
        self._credentials = None

    @property
    def provider_id(self) -> str:
        """Return the unique provider identifier string ('gcp')."""
        return "gcp"

    @property
    def provider(self) -> str:
        """Return the provider identifier string (alias for provider_id)."""
        return "gcp"

    @property
    def display_name(self) -> str:
        """Return the human-readable provider name shown in the UI switcher."""
        return "Google Cloud (GCP)"

    @property
    def icon_name(self) -> str:
        """Return the FreeDesktop symbolic icon name for the context switcher button."""
        return "network-workgroup-symbolic"

    @property
    def context_title(self) -> str:
        """Return the localized context title for dialog headers."""
        return _("GCP Project")

    @property
    def context_subtitle(self) -> str:
        """Return the localized subtitle with active GCP project ID."""
        return _("GCP Project: %s") % (self.project_id or _("Detecting..."))

    @property
    def context_btn_tooltip(self) -> str:
        """Return the localized tooltip for the project switcher button."""
        return _("Switch GCP Project")

    @property
    def loading_message(self) -> str:
        """Return the localized message shown while querying GCP secrets."""
        return _("Querying GCP Secret Manager...")

    @property
    def empty_message(self) -> str:
        """Return the localized message shown when no secrets exist in the project."""
        return _("No secrets found in this GCP project.")

    @property
    def error_message(self) -> str:
        """Return the localized message shown when connection or query fails."""
        return _("Could not connect to Google Cloud.")

    @property
    def supports_version_toggling(self) -> bool:
        """Return True indicating GCP supports enabling and disabling versions."""
        return True

    @property
    def supports_version_destroy(self) -> bool:
        """Return True indicating GCP supports permanently destroying versions."""
        return True

    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        """Open the modal dialog to browse and select a GCP project.

        Args:
            parent_window: GTK parent window to transient the dialog for.
            on_success: Callback function invoked after project selection.
        """
        from src.ui.dialogs import show_change_project_dialog

        def on_confirm(new_project_id: str) -> None:
            """Update active GCP project ID and trigger completion callback."""
            self.project_id = new_project_id
            on_success()

        show_change_project_dialog(parent_window, self, on_confirm)

    def toggle_version_state(self, version: str | SecretVersionItem, enable: bool) -> None:
        """Enable or disable an individual GCP secret version.

        Args:
            version: SecretVersionItem or version resource name string.
            enable: True to enable the version, False to disable it.
        """
        name = version.name if isinstance(version, SecretVersionItem) else version
        if enable:
            self.enable_secret_version(name)
        else:
            self.disable_secret_version(name)

    def destroy_version(self, version: str | SecretVersionItem) -> None:
        """Permanently destroy the payload of an individual GCP secret version.

        Args:
            version: SecretVersionItem or version resource name string.
        """
        name = version.name if isinstance(version, SecretVersionItem) else version
        self.destroy_secret_version(name)


    def initialize_client(self) -> secretmanager_v1.SecretManagerServiceClient:
        """Initialize or return existing SecretManagerServiceClient.

        Returns:
            secretmanager_v1.SecretManagerServiceClient: Initialized GCP client.

        Raises:
            RuntimeError: If GCP credentials cannot be found or authentication fails.
        """
        if self._client is not None:
            return self._client


        try:
            self._credentials, detected_project = google.auth.default()
            if not self._project_id and detected_project:
                self._project_id = detected_project
        except DefaultCredentialsError as exc:
            raise RuntimeError(
                "No se encontraron credenciales de GCP activas.\n"
                "Ejecuta en tu terminal:\n"
                "  gcloud auth application-default login\n"
                "o configura la variable de entorno GOOGLE_APPLICATION_CREDENTIALS."
            ) from exc
        except GoogleAuthError as exc:
            raise RuntimeError(f"Error de autenticación con GCP: {exc}") from exc

        self._client = secretmanager_v1.SecretManagerServiceClient(credentials=self._credentials)
        return self._client

    @property
    def project_id(self) -> Optional[str]:
        """Return the active GCP project ID, autodetecting if not explicitly set."""
        if not self._project_id:
            self._project_id = self.detect_project_id()
        return self._project_id

    @project_id.setter
    def project_id(self, val: Optional[str]) -> None:
        """Set or update the active GCP project ID."""
        self._project_id = val.strip() if val else None

    @classmethod
    def detect_project_id(cls) -> Optional[str]:
        """Detect the active GCP project from environment variables, gcloud config files, or ADC.

        Returns:
            Optional[str]: Detected GCP project identifier or None if undetected.
        """
        # 1. Environment variables
        for env_var in ("GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT", "CLOUDSDK_CORE_PROJECT"):
            val = os.getenv(env_var)
            if val and val.strip():
                return val.strip()

        # 2. Read gcloud active configuration directly from file (instant, zero subprocess overhead, no auth prompts)
        try:
            config_dir = os.path.expanduser("~/.config/gcloud")
            active_config_path = os.path.join(config_dir, "active_config")
            config_name = "default"
            if os.path.exists(active_config_path):
                with open(active_config_path, "r", encoding="utf-8") as f:
                    c = f.read().strip()
                    if c:
                        config_name = c

            config_file = os.path.join(config_dir, "configurations", f"config_{config_name}")
            if os.path.exists(config_file):
                import configparser
                parser = configparser.ConfigParser()
                parser.read(config_file)
                if parser.has_option("core", "project"):
                    proj = parser.get("core", "project").strip()
                    if proj:
                        return proj
        except Exception:
            pass

        # 3. Application Default Credentials
        try:
            _, project = google.auth.default()
            if project and project.strip():
                return project.strip()
        except Exception:
            pass

        return None

    def list_secrets(self, project_id: Optional[str] = None) -> List[SecretItem]:
        """List all secrets in the given or active GCP project.

        Args:
            project_id: Optional GCP project ID to query. If None, uses active project.

        Returns:
            List[SecretItem]: List of normalized secret item instances.

        Raises:
            ValueError: If no GCP project ID is specified or detected.
            PermissionDeniedError: If caller lacks Secret Manager Viewer/Accessor role.
            ProviderError: If the Google API request fails.
        """
        client = self.initialize_client()
        active_project = project_id or self.project_id
        if not active_project:
            raise ValueError("No se ha especificado ningún Project ID de GCP.")

        parent = f"projects/{active_project}"
        secrets: List[SecretItem] = []

        try:
            request = secretmanager_v1.ListSecretsRequest(parent=parent)
            page_result = client.list_secrets(request=request)

            for secret in page_result:
                # secret.name is projects/{project}/secrets/{secret_id}
                secret_id = secret.name.split("/")[-1]
                create_dt = _parse_timestamp(secret.create_time)

                repl_type = "AUTOMATIC"
                locations = []
                if secret.replication.automatic:
                    repl_type = "AUTOMATIC"
                elif secret.replication.user_managed:
                    repl_type = "USER_MANAGED"
                    locations = [replica.location for replica in secret.replication.user_managed.replicas]

                secrets.append(
                    SecretItem(
                        name=secret.name,
                        secret_id=secret_id,
                        create_time=create_dt,
                        labels=dict(secret.labels) if secret.labels else {},
                        replication_type=repl_type,
                        locations=locations,
                    )
                )

            secrets.sort(key=lambda s: s.secret_id.lower())
            return secrets

        except PermissionDenied as exc:
            raise PermissionDeniedError(
                f"Permiso denegado para el proyecto '{active_project}'.\n"
                "Asegúrate de tener asignado el rol 'Secret Manager Viewer' o 'Secret Manager Secret Accessor'.",
                provider="gcp",
                original_error=exc,
            ) from exc
        except NotFound as exc:
            raise ResourceNotFoundError(
                f"El proyecto '{active_project}' no fue encontrado en GCP.",
                provider="gcp",
                original_error=exc,
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(f"Error en la API de GCP Secret Manager: {exc.message}", provider="gcp", original_error=exc) from exc

    def list_versions(self, secret_full_name: str) -> List[SecretVersionItem]:
        """List all versions of a specific secret.

        Args:
            secret_full_name: Resource name (projects/.../secrets/...).

        Returns:
            List[SecretVersionItem]: Chronologically ordered versions.

        Raises:
            ResourceNotFoundError: If the secret does not exist.
            PermissionDeniedError: If permission is denied.
            ProviderError: If the API request fails.
        """
        client = self.initialize_client()
        request = secretmanager_v1.ListSecretVersionsRequest(parent=secret_full_name)
        versions: List[SecretVersionItem] = []

        try:
            for v in client.list_secret_versions(request=request):
                version_id = v.name.split("/")[-1]
                create_dt = _parse_timestamp(v.create_time)
                destroy_dt = _parse_timestamp(v.destroy_time)
                state_str = secretmanager_v1.SecretVersion.State(v.state).name

                versions.append(
                    SecretVersionItem(
                        version_id=version_id,
                        name=v.name,
                        state=state_str,
                        create_time=create_dt,
                        destroy_time=destroy_dt,
                    )
                )

            # Sort descending by version number
            def parse_ver_id(ver: SecretVersionItem) -> int:
                """Extract numerical version identifier for descending sorting."""
                try:
                    return int(ver.version_id)
                except ValueError:
                    return 0

            versions.sort(key=parse_ver_id, reverse=True)
            return versions

        except PermissionDenied as exc:
            raise PermissionDeniedError("Permiso denegado al listar las versiones del secreto.", provider="gcp", original_error=exc) from exc
        except NotFound as exc:
            raise ResourceNotFoundError(f"El secreto '{secret_full_name}' no existe.", provider="gcp", original_error=exc) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(f"Error al obtener versiones del secreto: {exc.message}", provider="gcp", original_error=exc) from exc

    def access_secret_payload(self, version_full_name: str) -> Tuple[str, bool]:
        """Fetch the payload of a specific secret version.

        Args:
            version_full_name: Full resource path of the target secret version.

        Returns:
            Tuple[str, bool]: Decoded payload string and is_binary boolean flag.

        Raises:
            ResourceNotFoundError: If the version was destroyed or does not exist.
            PermissionDeniedError: If caller lacks Secret Accessor role.
            ProviderError: If the API call fails.
        """
        client = self.initialize_client()
        request = secretmanager_v1.AccessSecretVersionRequest(name=version_full_name)

        try:
            response = client.access_secret_version(request=request)
            payload_bytes = response.payload.data

            try:
                decoded_str = payload_bytes.decode("utf-8")
                return decoded_str, False
            except UnicodeDecodeError:
                # If binary, return hex representation
                hex_str = payload_bytes.hex(" ")
                return f"[Datos binarios - {len(payload_bytes)} bytes]\n\n{hex_str}", True

        except PermissionDenied as exc:
            raise PermissionDeniedError(
                "Permiso denegado para acceder al valor del secreto.\n"
                "Se requiere el rol 'roles/secretmanager.secretAccessor'.",
                provider="gcp",
                original_error=exc,
            ) from exc
        except NotFound as exc:
            raise ResourceNotFoundError(
                f"La versión '{version_full_name}' no existe o fue destruida.",
                provider="gcp",
                original_error=exc,
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(f"Error al acceder al secreto: {exc.message}", provider="gcp", original_error=exc) from exc

    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> SecretItem:
        """Create a new secret and add its initial version payload.

        Args:
            secret_id: Short identifier for the secret.
            payload_data: Secret string payload.
            labels: Optional key-value dictionary of labels.
            description: Optional human-readable description.
            project_id: Optional target GCP project ID.

        Returns:
            SecretItem: Newly created secret metadata.

        Raises:
            ValueError: If project ID is missing.
            PermissionError: If caller lacks secretManager.admin role.
            RuntimeError: If creation fails.
        """
        client = self.initialize_client()
        active_project = project_id or self.project_id
        if not active_project:
            raise ValueError("No se ha especificado ningún Project ID de GCP.")

        parent = f"projects/{active_project}"
        secret_payload = secretmanager_v1.Secret(
            replication=secretmanager_v1.Replication(
                automatic=secretmanager_v1.Replication.Automatic()
            ),
            labels=labels or {},
        )

        try:
            created_secret = client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": secret_id,
                    "secret": secret_payload,
                }
            )

            if payload_data:
                self.add_secret_version(created_secret.name, payload_data)

            return SecretItem(
                name=created_secret.name,
                secret_id=secret_id,
                create_time=_parse_timestamp(created_secret.create_time),
                labels=dict(created_secret.labels) if created_secret.labels else {},
                replication_type="AUTOMATIC",
                locations=[],
            )
        except PermissionDenied as exc:
            raise PermissionError(
                "Permiso denegado para crear secretos en el proyecto.\n"
                "Se requiere el rol 'roles/secretmanager.admin'."
            ) from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"Error al crear el secreto: {exc.message}") from exc

    def add_secret_version(self, secret_full_name: str, payload_data: str) -> SecretVersionItem:
        """Add a new version to an existing secret.

        Args:
            secret_full_name: Resource path of parent secret.
            payload_data: New payload string.

        Returns:
            SecretVersionItem: Newly created version metadata.

        Raises:
            PermissionError: If caller lacks version manager permissions.
            RuntimeError: If API call fails.
        """
        client = self.initialize_client()
        payload_bytes = payload_data.encode("utf-8")

        try:
            version = client.add_secret_version(
                request={
                    "parent": secret_full_name,
                    "payload": {"data": payload_bytes},
                }
            )
            version_id = version.name.split("/")[-1]
            state_str = secretmanager_v1.SecretVersion.State(version.state).name

            return SecretVersionItem(
                version_id=version_id,
                name=version.name,
                state=state_str,
                create_time=_parse_timestamp(version.create_time),
                destroy_time=_parse_timestamp(version.destroy_time),
            )
        except PermissionDenied as exc:
            raise PermissionError(
                "Permiso denegado para añadir una nueva versión al secreto.\n"
                "Se requiere el rol 'roles/secretmanager.secretVersionManager' o 'roles/secretmanager.admin'."
            ) from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"Error al añadir versión: {exc.message}") from exc

    def enable_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Enables a previously disabled secret version."""
        client = self.initialize_client()
        try:
            version = client.enable_secret_version(request={"name": version_full_name})
            version_id = version.name.split("/")[-1]
            state_str = secretmanager_v1.SecretVersion.State(version.state).name
            return SecretVersionItem(
                version_id=version_id,
                name=version.name,
                state=state_str,
                create_time=_parse_timestamp(version.create_time),
                destroy_time=_parse_timestamp(version.destroy_time),
            )
        except PermissionDenied as exc:
            raise PermissionError("Permiso denegado para habilitar la versión.") from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"Error al habilitar la versión: {exc.message}") from exc

    def disable_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Disables a secret version so its payload cannot be accessed."""
        client = self.initialize_client()
        try:
            version = client.disable_secret_version(request={"name": version_full_name})
            version_id = version.name.split("/")[-1]
            state_str = secretmanager_v1.SecretVersion.State(version.state).name
            return SecretVersionItem(
                version_id=version_id,
                name=version.name,
                state=state_str,
                create_time=_parse_timestamp(version.create_time),
                destroy_time=_parse_timestamp(version.destroy_time),
            )
        except PermissionDenied as exc:
            raise PermissionError("Permiso denegado para deshabilitar la versión.") from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"Error al deshabilitar la versión: {exc.message}") from exc

    def destroy_secret_version(self, version_full_name: str) -> SecretVersionItem:
        """Irreversibly destroys the payload of a secret version."""
        client = self.initialize_client()
        try:
            version = client.destroy_secret_version(request={"name": version_full_name})
            version_id = version.name.split("/")[-1]
            state_str = secretmanager_v1.SecretVersion.State(version.state).name
            return SecretVersionItem(
                version_id=version_id,
                name=version.name,
                state=state_str,
                create_time=_parse_timestamp(version.create_time),
                destroy_time=_parse_timestamp(version.destroy_time),
            )
        except PermissionDenied as exc:
            raise PermissionError("Permiso denegado para destruir la versión.") from exc
        except GoogleAPICallError as exc:
            raise RuntimeError(f"Error al destruir la versión: {exc.message}") from exc

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
                "Permiso denegado para eliminar el secreto.\n"
                "Se requiere el rol 'roles/secretmanager.admin'.",
                provider="gcp",
                original_error=exc,
            ) from exc
        except GoogleAPICallError as exc:
            raise ProviderError(f"Error al eliminar el secreto: {exc.message}", provider="gcp", original_error=exc) from exc

    def list_available_projects(self) -> List[GCPProjectItem]:
        """Lists active GCP projects accessible to the authenticated credentials."""
        self.initialize_client()
        from google.auth.transport.requests import AuthorizedSession

        session = AuthorizedSession(self._credentials)
        url = "https://cloudresourcemanager.googleapis.com/v1/projects?pageSize=300"
        projects: List[GCPProjectItem] = []

        try:
            while url:
                resp = session.get(url, timeout=12)
                if resp.status_code != 200:
                    raise RuntimeError(f"Error {resp.status_code} al consultar proyectos: {resp.text}")

                data = resp.json()
                for p in data.get("projects", []):
                    # Only active projects
                    if p.get("lifecycleState") == "ACTIVE" or not p.get("lifecycleState"):
                        p_id = p.get("projectId", "")
                        p_name = p.get("name", p_id)
                        projects.append(
                            GCPProjectItem(
                                project_id=p_id,
                                name=p_name,
                                lifecycle_state=p.get("lifecycleState", "ACTIVE"),
                            )
                        )

                next_token = data.get("nextPageToken")
                if next_token:
                    url = f"https://cloudresourcemanager.googleapis.com/v1/projects?pageSize=300&pageToken={next_token}"
                else:
                    url = None

            projects.sort(key=lambda p: p.project_id.lower())
            return projects
        except Exception as exc:
            raise RuntimeError(f"No fue posible consultar los proyectos de GCP: {exc}") from exc


