"""Providers package providing secret manager implementations for multiple cloud platforms."""

from src.providers.ansible import AnsibleVaultClient
from src.providers.aws import AWSSecretClient
from src.providers.azure import AzureSecretClient
from src.providers.base import BaseSecretProvider
from src.providers.gcp import GCPSecretClient
from src.providers.kubernetes import KubernetesClient
from src.providers.ssm import SSMClient
from src.providers.vault import VaultClient

__all__ = [
    "BaseSecretProvider",
    "GCPSecretClient",
    "AWSSecretClient",
    "AzureSecretClient",
    "AnsibleVaultClient",
    "VaultClient",
    "SSMClient",
    "KubernetesClient",
]
