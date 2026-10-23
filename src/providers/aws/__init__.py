"""Amazon Web Services (AWS) Secrets Manager provider package."""

from src.providers.aws.client import AWSSecretClient
from src.providers.aws.discovery import (
    COMMON_AWS_REGIONS,
    detect_profile,
    detect_region,
    list_available_profiles,
    list_available_regions,
)
from src.providers.aws.helpers import parse_aws_secret_item, parse_aws_version_item

__all__ = [
    "AWSSecretClient",
    "COMMON_AWS_REGIONS",
    "detect_profile",
    "detect_region",
    "list_available_profiles",
    "list_available_regions",
    "parse_aws_secret_item",
    "parse_aws_version_item",
]
