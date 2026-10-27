"""Domain-specific exceptions for Gossip secret management."""

from __future__ import annotations

from typing import Optional


class GossipError(Exception):
    """Base exception for all Gossip application errors."""

    def __init__(self, message: str, original_error: Optional[BaseException] = None) -> None:
        """Initialize a GossipError.

        Args:
            message: Human-readable error description.
            original_error: Underlying exception caught from a lower-level library, if any.
        """
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class ProviderError(GossipError):
    """Base exception for secret provider operations."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        original_error: Optional[BaseException] = None,
    ) -> None:
        """Initialize a ProviderError.

        Args:
            message: Human-readable error description.
            provider: Identifier of the provider where the error occurred (e.g., 'gcp', 'aws').
            original_error: Underlying exception caught from the provider SDK, if any.
        """
        super().__init__(message, original_error=original_error)
        self.provider = provider


class AuthenticationError(ProviderError):
    """Raised when authentication credentials are invalid or missing."""


class PermissionDeniedError(ProviderError, PermissionError):
    """Raised when the user lacks permissions for a specific operation."""


class ResourceNotFoundError(ProviderError, FileNotFoundError):
    """Raised when a secret, project, vault, or file does not exist."""


class SecretConflictError(ProviderError, ValueError):
    """Raised when attempting to create a secret that already exists."""


class ProviderOperationError(ProviderError, RuntimeError):
    """Raised when a provider call fails for a reason other than the specific cases above."""


class ConfigurationError(ProviderError):
    """Raised when provider configuration or context is missing or invalid."""
