"""Google Cloud Platform Secret Manager provider package."""

from google.cloud import secretmanager_v1

from src.providers.gcp.client import GCPSecretClient
from src.providers.gcp.discovery import detect_project_id, fetch_available_projects
from src.providers.gcp.helpers import _parse_timestamp, parse_secret_item, parse_version_item

__all__ = [
    "GCPSecretClient",
    "_parse_timestamp",
    "detect_project_id",
    "fetch_available_projects",
    "parse_secret_item",
    "parse_version_item",
    "secretmanager_v1",
]
