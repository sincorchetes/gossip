"""Microsoft Azure Key Vault provider package."""

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.providers.azure.client import AzureSecretClient
from src.providers.azure.discovery import (
    detect_vault_name,
    list_available_vaults,
)
from src.providers.azure.helpers import (
    parse_azure_secret_item,
    parse_azure_version_item,
)

__all__ = [
    "AzureSecretClient",
    "DefaultAzureCredential",
    "SecretClient",
    "detect_vault_name",
    "list_available_vaults",
    "parse_azure_secret_item",
    "parse_azure_version_item",
]
