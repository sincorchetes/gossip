"""The list of providers and the settings each one takes, in one place.

The command line, the application and the main window all build their clients from this
registry. Adding a provider means writing its client and adding one ``ProviderSpec`` here: the
parser gets its options, the application constructs it (and restores its saved context) and the
window lists it, without touching those three modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Mapping, Optional, Tuple

from src.i18n import _

if TYPE_CHECKING:
    from src.providers.base import BaseSecretProvider

# Clients are imported only when one is built: the command line (--help, --version, the
# self-test) must not load every cloud SDK just to know which options exist.


@dataclass(frozen=True)
class Option:
    """A command-line option that sets up a provider.

    Attributes:
        flag: The option as typed, e.g. ``--vault-addr``.
        name: Name of the value (also the keyword of GossipApplication / run_app).
        help: Returns the translated help text (called when the parser is built).
        short: Optional one-letter form, e.g. ``-p``.
    """

    flag: str
    name: str
    help: Callable[[], str]
    short: Optional[str] = None


@dataclass(frozen=True)
class ProviderSpec:
    """How to build one provider from the options the user gave.

    Attributes:
        id: Provider identifier ('gcp', 'vault', ...).
        client: Where the provider class lives, as ``module:Class``.
        arguments: Constructor keyword to option name, e.g. ``{"project_id": "project_id"}``.
        options: The command-line options this provider introduces.
    """

    id: str
    client: str
    arguments: Mapping[str, str]
    options: Tuple[Option, ...] = ()

    def create(self, values: Mapping[str, Any]) -> BaseSecretProvider:
        """Instantiate the client with the options that apply to it."""
        module, _sep, class_name = self.client.partition(":")
        factory = getattr(import_module(module), class_name)
        return factory(**{kw: values.get(name) for kw, name in self.arguments.items()})

    def is_explicit(self, values: Mapping[str, Any]) -> bool:
        """True when the user chose this provider's context on the command line."""
        return any(values.get(name) for name in self.arguments.values())


_AWS_ARGUMENTS = {"profile_name": "aws_profile", "region_name": "aws_region"}

PROVIDERS: Tuple[ProviderSpec, ...] = (
    ProviderSpec(
        "gcp",
        "src.providers.gcp:GCPSecretClient",
        {"project_id": "project_id"},
        (
            Option(
                "--project",
                "project_id",
                lambda: _("GCP project ID to query (skips autodetection)"),
                short="-p",
            ),
        ),
    ),
    ProviderSpec(
        "aws",
        "src.providers.aws:AWSSecretClient",
        _AWS_ARGUMENTS,
        (
            Option(
                "--aws-profile",
                "aws_profile",
                lambda: _("AWS credentials profile to use (skips autodetection)"),
            ),
            Option(
                "--aws-region",
                "aws_region",
                lambda: _("AWS region to query (e.g. eu-west-1, us-east-1)"),
            ),
        ),
    ),
    ProviderSpec(
        "azure",
        "src.providers.azure:AzureSecretClient",
        {"vault_name": "azure_vault"},
        (
            Option(
                "--azure-vault",
                "azure_vault",
                lambda: _("Azure Key Vault name or URL (skips autodetection)"),
            ),
        ),
    ),
    ProviderSpec(
        "ansible",
        "src.providers.ansible:AnsibleVaultClient",
        {"vault_file": "ansible_vault", "password_file": "ansible_password_file"},
        (
            Option(
                "--ansible-vault",
                "ansible_vault",
                lambda: _("Path to the encrypted Ansible Vault file (skips autodetection)"),
            ),
            Option(
                "--ansible-password-file",
                "ansible_password_file",
                lambda: _("Path to the Ansible Vault password file (must be readable only by you)"),
            ),
        ),
    ),
    ProviderSpec(
        "vault",
        "src.providers.vault:VaultClient",
        {"address": "vault_addr", "mount": "vault_mount"},
        (
            Option(
                "--vault-addr",
                "vault_addr",
                lambda: _("HashiCorp Vault / OpenBao server URL (default: VAULT_ADDR)"),
            ),
            Option(
                "--vault-mount",
                "vault_mount",
                lambda: _("KV v2 mount path on the Vault server (default: secret)"),
            ),
        ),
    ),
    # Parameter Store shares the profile and region options of Secrets Manager
    ProviderSpec("ssm", "src.providers.ssm:SSMClient", _AWS_ARGUMENTS),
    ProviderSpec(
        "k8s",
        "src.providers.kubernetes:KubernetesClient",
        {"context": "kube_context", "namespace": "kube_namespace"},
        (
            Option(
                "--kube-context",
                "kube_context",
                lambda: _("Kubeconfig context to use (default: the current context)"),
            ),
            Option(
                "--kube-namespace",
                "kube_namespace",
                lambda: _(
                    "Kubernetes namespace whose Secrets to manage (default: the context namespace)"
                ),
            ),
        ),
    ),
)

PROVIDER_IDS: Tuple[str, ...] = tuple(spec.id for spec in PROVIDERS)


def all_options() -> List[Option]:
    """Every provider option, in registry order."""
    return [option for spec in PROVIDERS for option in spec.options]


def option_names() -> List[str]:
    """Names of every provider option."""
    return [option.name for option in all_options()]


def create_clients(
    values: Mapping[str, Any], overrides: Optional[Mapping[str, BaseSecretProvider]] = None
) -> Dict[str, BaseSecretProvider]:
    """Build one client per provider, in order.

    Args:
        values: Option values by name (missing or None means "not given").
        overrides: Ready-made clients that replace the ones that would be built.
    """
    overrides = overrides or {}
    return {spec.id: overrides.get(spec.id) or spec.create(values) for spec in PROVIDERS}
