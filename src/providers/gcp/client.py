"""Google Cloud Platform Secret Manager client class."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

import google.auth
from google.auth.exceptions import DefaultCredentialsError, GoogleAuthError
from google.cloud import secretmanager_v1

from src.i18n import _
from src.models import SecretVersionItem
from src.providers.base import BaseSecretProvider
from src.providers.gcp.discovery import detect_project_id
from src.providers.gcp.ops import GCPOperationsMixin


class GCPSecretClient(GCPOperationsMixin, BaseSecretProvider):
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
    def supports_metadata_edit(self) -> bool:
        """Labels of a secret can be edited."""
        return True

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
            self.project_id = new_project_id
            on_success()

        show_change_project_dialog(parent_window, self, on_confirm)

    def toggle_version_state(self, version: str | SecretVersionItem, enable: bool) -> None:
        """Enable or disable an individual GCP secret version."""
        name = version.name if isinstance(version, SecretVersionItem) else version
        if enable:
            self.enable_secret_version(name)
        else:
            self.disable_secret_version(name)

    def destroy_version(self, version: str | SecretVersionItem) -> None:
        """Permanently destroy the payload of an individual GCP secret version."""
        name = version.name if isinstance(version, SecretVersionItem) else version
        self.destroy_secret_version(name)

    def initialize_client(self) -> secretmanager_v1.SecretManagerServiceClient:
        """Initialize or return existing SecretManagerServiceClient."""
        if self._client is not None:
            return self._client

        try:
            self._credentials, detected_project = google.auth.default()
            if not self._project_id and detected_project:
                self._project_id = detected_project
        except DefaultCredentialsError as exc:
            raise RuntimeError(
                _(
                    "No active GCP credentials found.\n"
                    "Run in your terminal:\n"
                    "  gcloud auth application-default login\n"
                    "or set the GOOGLE_APPLICATION_CREDENTIALS environment variable."
                )
            ) from exc
        except GoogleAuthError as exc:
            raise RuntimeError(f"{_('GCP authentication error')}: {exc}") from exc

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

    def saved_context(self) -> Dict[str, str]:
        """Return the explicitly chosen project."""
        return {"project": self._project_id} if self._project_id else {}

    def restore_context(self, context: Dict[str, str]) -> None:
        """Re-select the remembered project."""
        if context.get("project"):
            self._project_id = context["project"]
            self._client = None

    @classmethod
    def detect_project_id(cls) -> Optional[str]:
        """Detect the active GCP project from environment variables, gcloud config files, or ADC."""
        return detect_project_id()
