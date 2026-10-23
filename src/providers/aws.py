"""Amazon Web Services (AWS) Secrets Manager provider implementation."""

from __future__ import annotations

from typing import Any, Callable, List, Optional

import boto3

from src.i18n import _
from src.providers.aws_discovery import (
    COMMON_AWS_REGIONS,
    detect_profile,
    detect_region,
    list_available_profiles,
    list_available_regions,
)
from src.providers.aws_ops import AWSOperationsMixin
from src.providers.base import BaseSecretProvider


class AWSSecretClient(AWSOperationsMixin, BaseSecretProvider):
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
        self._profile_name = profile_name
        self._region_name = region_name
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
        """Update active AWS profile and region simultaneously, resetting client cache."""
        self._profile_name = profile.strip() if profile else "default"
        self._region_name = region.strip() if region else "us-east-1"
        self._session = None
        self._client = None

    @classmethod
    def detect_profile(cls) -> str:
        """Detect active AWS credentials profile from environment variables or local configuration."""
        return detect_profile(cls.list_available_profiles)

    @classmethod
    def detect_region(cls) -> str:
        """Detect active AWS target region from environment variables, session, or default."""
        return detect_region()

    @classmethod
    def list_available_profiles(cls) -> List[str]:
        """List all configured AWS profiles available on the system."""
        return list_available_profiles()

    @classmethod
    def list_available_regions(cls) -> List[str]:
        """List standard AWS regions supported by Secrets Manager."""
        return list_available_regions()


__all__ = ["AWSSecretClient", "COMMON_AWS_REGIONS"]
