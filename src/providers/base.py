"""Abstract base class defining the contract for secret management providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.models import SecretItem, SecretVersionItem


class BaseSecretProvider(ABC):
    """Abstract interface for all secret providers (GCP, AWS, Azure, Ansible, etc.).

    Adheres to the Strategy Pattern and Open-Closed Principle (OCP) so new
    providers can be integrated without modifying UI or controller logic.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier (e.g. 'gcp', 'aws', 'azure', 'ansible')."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """User-friendly name shown in the UI switcher."""

    @property
    @abstractmethod
    def icon_name(self) -> str:
        """Symbolic icon representing the context configuration action."""

    @property
    @abstractmethod
    def context_subtitle(self) -> str:
        """Subtitle for the HeaderBar showing active context (project, profile, vault, etc.)."""

    @property
    @abstractmethod
    def context_btn_tooltip(self) -> str:
        """Tooltip text for the context switcher button."""

    @property
    @abstractmethod
    def loading_message(self) -> str:
        """Message displayed while querying secrets."""

    @property
    @abstractmethod
    def empty_message(self) -> str:
        """Message displayed when no secrets are found."""

    @property
    @abstractmethod
    def error_message(self) -> str:
        """Message displayed upon connection or query failure."""

    @property
    def supports_version_toggling(self) -> bool:
        """Whether this provider supports enabling/disabling individual versions."""
        return False

    @property
    def supports_version_destroy(self) -> bool:
        """Whether this provider supports permanently destroying a specific version payload."""
        return False

    @abstractmethod
    def list_secrets(self) -> List[SecretItem]:
        """List all accessible secrets for the active context.

        Returns:
            List[SecretItem]: List of normalized secret item instances.

        Raises:
            ProviderError: If communication or authorization with the provider fails.
        """

    @abstractmethod
    def list_versions(self, secret_name: str) -> List[SecretVersionItem]:
        """List all versions of a specific secret.

        Args:
            secret_name: Unique resource identifier or ARN of the parent secret.

        Returns:
            List[SecretVersionItem]: Chronologically or sequentially ordered versions.

        Raises:
            ProviderError: If retrieval fails.
        """

    @abstractmethod
    def access_secret_payload(
        self, secret_name: str, version: Optional[str] = None
    ) -> Tuple[str, bool]:
        """Retrieve the secret payload content.

        Args:
            secret_name: Identifier or ARN of the secret.
            version: Optional version identifier or stage. If None, retrieves the latest active version.

        Returns:
            Tuple[str, bool]: A tuple containing (payload_string, is_binary_flag).

        Raises:
            ResourceNotFoundError: If the secret or version does not exist.
            ProviderError: If access fails.
        """

    @abstractmethod
    def create_secret(
        self,
        secret_id: str,
        payload_data: str,
        labels: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> SecretItem:
        """Create a new secret and store its initial payload version.

        Args:
            secret_id: Human-readable secret name / identifier.
            payload_data: Secret string or payload data to store.
            labels: Optional dictionary of key-value tags or labels.
            description: Optional human-readable description note.

        Returns:
            SecretItem: Newly created normalized secret item.

        Raises:
            SecretConflictError: If a secret with this identifier already exists.
            ProviderError: If creation fails.
        """

    @abstractmethod
    def add_secret_version(self, secret_name: str, payload_data: str) -> SecretVersionItem:
        """Add a new version payload to an existing secret.

        Args:
            secret_name: Full resource path or identifier of the target secret.
            payload_data: String payload content for the new version.

        Returns:
            SecretVersionItem: Newly created secret version item.

        Raises:
            ResourceNotFoundError: If the parent secret does not exist.
            ProviderError: If operation fails.
        """

    @abstractmethod
    def delete_secret(self, secret_name_or_id: str) -> None:
        """Permanently delete a secret and all associated versions.

        Args:
            secret_name_or_id: Full resource name or short identifier of the secret to delete.

        Raises:
            ResourceNotFoundError: If the secret does not exist.
            ProviderError: If deletion fails.
        """

    def toggle_version_state(self, version: SecretVersionItem, enable: bool) -> None:
        """Enable or disable an individual version if supported by provider.

        Args:
            version: Version item to modify.
            enable: True to enable the version, False to disable it.

        Raises:
            NotImplementedError: If the provider does not support version toggling.
            ProviderError: If operation fails.
        """
        raise NotImplementedError(f"Version state toggling is not supported by {self.display_name}")

    def destroy_version(self, version: SecretVersionItem) -> None:
        """Permanently destroy a version payload if supported by provider.

        Args:
            version: Version item to destroy.

        Raises:
            NotImplementedError: If the provider does not support version destruction.
            ProviderError: If operation fails.
        """
        raise NotImplementedError(f"Version destroying is not supported by {self.display_name}")

    @abstractmethod
    def open_context_dialog(self, parent_window: Any, on_success: Callable[[], None]) -> None:
        """Open the provider-specific context configuration modal dialog.

        Args:
            parent_window: GTK parent window to transient the dialog for.
            on_success: Callback function invoked when the context is successfully changed.
        """
