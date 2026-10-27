"""Domain models representing secrets, versions, and multi-cloud provider contexts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.i18n import _


@dataclass
class SecretVersionItem:
    """Normalized data representation of an individual secret version across cloud providers.

    Attributes:
        version_id: Unique identifier or sequential version number (e.g., '1', UUID).
        name: Fully qualified resource identifier or ARN.
        state: Lifecycle status ('ENABLED', 'DISABLED', 'DESTROYED').
        stages: Version stage labels (e.g., AWS 'AWSCURRENT', 'AWSPREVIOUS').
        create_time: Timestamp when this version was created.
        destroy_time: Timestamp when this version was scheduled for destruction.
    """

    version_id: str
    name: str  # Full resource name: projects/.../secrets/.../versions/... or AWS Version ID/ARN
    state: str = "ENABLED"  # ENABLED, DISABLED, DESTROYED (GCP) or staging label (AWS)
    stages: List[str] = field(default_factory=list)
    create_time: Optional[datetime] = None
    destroy_time: Optional[datetime] = None

    @property
    def display_state(self) -> str:
        """Return a localized human-readable representation of the version's state or stage."""
        if self.stages:
            if "AWSCURRENT" in self.stages:
                other_stages = [s for s in self.stages if s != "AWSCURRENT"]
                if other_stages:
                    return f"{_('Current')} ({', '.join(other_stages)})"
                return _("Current")
            elif "AWSPREVIOUS" in self.stages:
                return _("Previous")
            return ", ".join(self.stages)

        clean_state = self.state.replace("STATE_", "")
        if clean_state == "ENABLED":
            return _("Enabled")
        elif clean_state == "DISABLED":
            return _("Disabled")
        elif clean_state == "DESTROYED":
            return _("Destroyed")
        return clean_state


@dataclass
class SecretItem:
    """Unified domain model representing a secret resource across supported providers.

    Attributes:
        name: Full resource path or cloud provider identifier / ARN.
        secret_id: Human-readable secret identifier / short name.
        provider: Cloud provider identifier ('gcp', 'aws', 'azure', 'ansible').
        description: Optional user-facing description or note.
        create_time: Creation timestamp.
        last_changed_date: Last modification timestamp.
        labels: Key-value tags or labels attached to the secret.
        replication_type: Replication policy (e.g., 'AUTOMATIC', 'SINGLE_REGION').
        locations: Cloud regions or locations where secret is replicated.
        kms_key_id: Customer-managed KMS encryption key ID or ARN if configured.
        versions: List of versions associated with this secret.
    """

    name: str  # Full resource name: projects/.../secrets/... or AWS Secret ARN
    secret_id: str  # Just the short name
    provider: str = "gcp"  # "gcp" | "aws" | "azure" | "ansible"
    description: Optional[str] = None
    create_time: Optional[datetime] = None
    last_changed_date: Optional[datetime] = None
    labels: Dict[str, str] = field(default_factory=dict)
    replication_type: str = "AUTOMATIC"
    locations: List[str] = field(default_factory=list)
    kms_key_id: Optional[str] = None
    versions: List[SecretVersionItem] = field(default_factory=list)

    @property
    def replication_summary(self) -> str:
        """Return a localized human-readable summary of the replication configuration."""
        if self.locations:
            return f"{_('Replicated')} ({', '.join(self.locations)})"
        if self.replication_type == "AUTOMATIC":
            return _("Automatic")
        if self.replication_type == "SINGLE_REGION":
            return _("Single region")
        return _("User managed")


@dataclass
class GCPProjectItem:
    """Google Cloud Platform project descriptor.

    Attributes:
        project_id: GCP project identifier (e.g., 'my-sample-project-123').
        name: Display name of the Google Cloud project.
        lifecycle_state: Project lifecycle state (e.g., 'ACTIVE', 'DELETE_REQUESTED').
    """

    project_id: str
    name: str
    lifecycle_state: str = "ACTIVE"


@dataclass
class AWSContextItem:
    """AWS configuration context holding active credentials profile and region.

    Attributes:
        profile: AWS CLI / SDK profile name (e.g., 'default', 'production').
        region: AWS region code (e.g., 'us-east-1', 'eu-west-1').
    """

    profile: str
    region: str


@dataclass
class AzureVaultItem:
    """Azure Key Vault context descriptor.

    Attributes:
        name: Azure Key Vault instance name.
        vault_uri: Fully-qualified vault URI (e.g., 'https://my-vault.vault.azure.net/').
        location: Optional Azure datacenter region (e.g., 'eastus').
    """

    name: str
    vault_uri: str
    location: Optional[str] = None


@dataclass
class AnsibleVaultItem:
    """Local Ansible Vault file context and decryption state.

    Attributes:
        file_path: Absolute or relative filesystem path to the Ansible Vault YAML file.
        has_password: True if an in-memory decryption password is currently cached.
        is_encrypted: True if file currently contains '$ANSIBLE_VAULT;' header.
    """

    file_path: str
    has_password: bool = False
    is_encrypted: bool = True
