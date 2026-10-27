# Domain Data Models

Gossip uses pure-Python dataclasses located in `src.models` as an **Anti-Corruption Layer (ACL)**. Instead of exposing cloud-specific SDK response objects (`google.cloud.secretmanager_v1.Secret`, `boto3` dicts, Azure `KeyVaultSecret`, or raw YAML maps) to the presentation layer, all providers map data directly into these normalized models.

## Architecture & Relationships

```mermaid
classDiagram
    class SecretItem {
        +str name
        +str secret_id
        +str provider
        +Optional~str~ description
        +Optional~datetime~ create_time
        +Optional~datetime~ last_changed_date
        +Dict~str, str~ labels
        +str replication_type
        +List~str~ locations
        +Optional~str~ kms_key_id
        +List~SecretVersionItem~ versions
        +replication_summary() str
    }

    class SecretVersionItem {
        +str version_id
        +str name
        +str state
        +List~str~ stages
        +Optional~datetime~ create_time
        +Optional~datetime~ destroy_time
        +display_state() str
    }

    class GCPProjectItem {
        +str project_id
        +str name
        +str lifecycle_state
    }

    class AWSContextItem {
        +str profile
        +str region
    }

    class AzureVaultItem {
        +str name
        +str vault_uri
        +Optional~str~ location
    }

    class AnsibleVaultItem {
        +str file_path
        +bool has_password
        +bool is_encrypted
    }

    SecretItem "1" *-- "many" SecretVersionItem : contains
```

## Core Models Overview

| Model | Purpose | Consumed By |
| :--- | :--- | :--- |
| `SecretItem` | High-level secret metadata, labels, replication, and child versions. | `MainWindow`, `SecretDialog`, all providers |
| `SecretVersionItem` | Secret version state, stages, lifecycle timestamps, and localized display state. | `MainWindow` versions table, add/destroy dialogs |
| `GCPProjectItem` | Google Cloud project identifier and display name. | Project selection dialog, `GCPSecretClient` |
| `AWSContextItem` | Active AWS CLI profile name and target region. | Context dialog, `AWSSecretClient` |
| `AzureVaultItem` | Azure Key Vault URI and resource location. | Vault selector dialog, `AzureSecretClient` |
| `AnsibleVaultItem` | File path, encryption state, and password cache indicator for local vaults. | Ansible file/unlock dialog, `AnsibleVaultClient` |

---

## API Specification (`src.models`)

::: src.models
    options:
      show_root_heading: true
      show_source: true
      members_order: source
