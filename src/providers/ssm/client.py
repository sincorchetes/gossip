"""AWS Systems Manager Parameter Store provider."""

from __future__ import annotations

from src.i18n import _
from src.providers.aws.client import AWSContextProvider
from src.providers.ssm.ops import SSMOperationsMixin


class SSMClient(SSMOperationsMixin, AWSContextProvider):
    """Parameter Store provider; shares the AWS profile and region selection."""

    @property
    def supports_metadata_edit(self) -> bool:
        """Tags can be edited."""
        return True

    @property
    def provider_id(self) -> str:
        """Return the unique provider identifier string ('ssm')."""
        return "ssm"

    @property
    def provider(self) -> str:
        """Return the provider identifier string (alias for provider_id)."""
        return "ssm"

    @property
    def display_name(self) -> str:
        """Return the human-readable provider name shown in the UI switcher."""
        return "AWS Systems Manager (Parameter Store)"

    @property
    def context_subtitle(self) -> str:
        """Return the subtitle with the active AWS profile and region."""
        return _("Parameter Store: %s (%s)") % (self.profile_name, self.region_name)

    @property
    def context_btn_tooltip(self) -> str:
        """Return the tooltip for the profile switcher button."""
        return _("Switch AWS Profile & Region")

    @property
    def loading_message(self) -> str:
        """Return the message shown while querying Parameter Store."""
        return _("Querying AWS Parameter Store...")

    @property
    def empty_message(self) -> str:
        """Return the message shown when the region has no parameters."""
        return _("No parameters found in this AWS region.")
