# Secret Providers Overview

The `src.providers` package encapsulates all interaction with secret management backends. Each provider inherits from [`BaseSecretProvider`](base.md) and translates vendor-specific SDK calls and exceptions into normalized domain structures.

---

## Feature Comparison Matrix

| Feature | Google Cloud (GCP) | Amazon Web Services (AWS) | Microsoft Azure (Key Vault) | Ansible Vault |
| :--- | :---: | :---: | :---: | :---: |
| **Provider ID** | `"gcp"` | `"aws"` | `"azure"` | `"ansible"` |
| **Underlying SDK** | `google-cloud-secret-manager` | `boto3` | `azure-keyvault-secrets` | `ansible-vault` & `PyYAML` |
| **Authentication** | ADC, `gcloud`, Service Account | AWS Credentials, Profiles, SSO | DefaultAzureCredential, CLI | Direct Password, `.vault_pass` |
| **Context Identifier** | GCP Project ID | AWS Profile & Region | Key Vault Name / URL | Vault File Path |
| **Version Toggling** | ✅ `ENABLED` / `DISABLED` | ❌ Not supported | ✅ `ENABLED` / `DISABLED` | ❌ Not supported |
| **Version Destruction** | ✅ Permanent payload purge | ❌ Not supported | ❌ Not supported | ❌ Not supported |
| **Secret Labels / Tags** | ✅ Labels dictionary | ✅ Tags dictionary | ✅ Tags dictionary | ❌ N/A (YAML variables) |
| **Context Dialog** | Searchable Project Dialog | Profile & Region Dialog | Vault Name / List Dialog | File Browser & Unlock Dialog |

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
)
```
