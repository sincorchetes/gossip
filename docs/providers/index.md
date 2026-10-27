# Secret Providers Overview

The `src.providers` package encapsulates all interaction with secret management backends. Each provider inherits from [`BaseSecretProvider`](base.md) and translates vendor-specific SDK calls and exceptions into normalized domain structures.

---

## Feature Comparison Matrix

| Feature | GCP | AWS Secrets Manager | AWS Parameter Store | Azure Key Vault | Ansible Vault | HashiCorp Vault / OpenBao | Kubernetes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Provider ID** | `"gcp"` | `"aws"` | `"ssm"` | `"azure"` | `"ansible"` | `"vault"` | `"k8s"` |
| **Client** | `google-cloud-secret-manager` | `boto3` | `boto3` | `azure-keyvault-secrets` | `ansible-vault` & `PyYAML` | Standard library (HTTP) | Standard library (HTTP) & `PyYAML` |
| **Authentication** | ADC, `gcloud`, service account | AWS credential chain, profiles, SSO | AWS credential chain, profiles, SSO | `DefaultAzureCredential`, CLI | Typed password or private `.vault_pass` | Token (`VAULT_TOKEN`, `~/.vault-token`, typed) | kubeconfig: token, certificate, `exec` plugin |
| **Context** | Project ID | Profile & region | Profile & region | Key Vault name / URL | Vault file path | Server, KV v2 mount, namespace | Context & namespace |
| **Version history** | ✅ | ✅ (staging labels) | ✅ (labels) | ✅ | ✅ last 5 saves | ✅ | ➖ single version |
| **Disable / enable version** | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ soft-delete / undelete | ❌ |
| **Destroy version** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Labels / tags** | ✅ labels | ✅ tags | ✅ tags | ✅ tags | ❌ (YAML variables) | ✅ custom metadata on create | ✅ labels |
| **Multi-key values** | ❌ | ❌ | ❌ | ❌ | ✅ typed YAML | ✅ JSON ↔ keys | ✅ JSON ↔ keys |
| **Delete behavior** | Irreversible | Recoverable 7 days (or immediate) | Irreversible | Soft-delete by the service | Irreversible (backups kept) | Metadata and all versions | Irreversible |
| **Edit labels / description** | ✅ labels | ✅ tags + description | ✅ tags | ✅ tags + content type | ❌ | ✅ custom metadata | ✅ labels |
| **Restore an older version** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ (no history) |
| **Create never overwrites** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ check-and-set | ✅ |
| **Context dialog** | Searchable project list | Profile & region | Profile & region | Vault name + discovered vaults | File browser & unlock | Address, mount, namespace, token | Context + namespace list |

All providers translate failures into the [domain exceptions](../api/exceptions.md), which also inherit from the matching built-in exceptions (`PermissionError`, `FileNotFoundError`, `ValueError`, `RuntimeError`). AWS and Azure use connection and read timeouts with two retries and report unreachable servers with a clear message.

---

## Public Exports

The package `src.providers` provides a single unified entry point:

```python
from src.providers import (
    BaseSecretProvider,
    GCPSecretClient,
    AWSSecretClient,
    AzureSecretClient,
    AnsibleVaultClient,
    VaultClient,
    SSMClient,
    KubernetesClient,
)
```

Each provider also implements two optional hooks used by the interface: `saved_context()` / `restore_context()` (the non-sensitive selections remembered between runs) and `lock()` (forget in-memory secret material on inactivity).
