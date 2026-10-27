# Modelos de Datos del Dominio

Gossip implementa dataclasses en Python puro en `src.models` actuando como una **Capa Anti-Corrupción (ACL)**. En lugar de exponer a la capa de presentación objetos directos de los SDK de cada nube (`google.cloud.secretmanager_v1.Secret`, diccionarios de `boto3`, objetos de Azure `KeyVaultSecret`, o estructuras YAML directas), todos los clientes traducen las respuestas a estos modelos tipados y estandarizados.

## Arquitectura y Relaciones

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

    SecretItem "1" *-- "many" SecretVersionItem : contiene
```

## Resumen de Modelos Principales

| Modelo | Propósito | Utilizado Por |
| :--- | :--- | :--- |
| `SecretItem` | Metadatos generales del secreto, etiquetas, replicación y versiones hijas. | `MainWindow`, `SecretDialog`, todos los proveedores |
| `SecretVersionItem` | Estado de la versión, etiquetas de ciclo de vida y estado traducido. | Tabla de versiones de `MainWindow`, diálogos de versiones |
| `GCPProjectItem` | Identificador de proyecto GCP y nombre legible. | Selector de proyecto, `GCPSecretClient` |
| `AWSContextItem` | Perfil de AWS CLI activo y región de destino. | Diálogo de contexto AWS, `AWSSecretClient` |
| `AzureVaultItem` | URI del Vault de Azure y región del recurso. | Selector de Vaults, `AzureSecretClient` |
| `AnsibleVaultItem` | Ruta del archivo, estado de cifrado y caché de contraseña. | Diálogo de desbloqueo, `AnsibleVaultClient` |

---

## Especificación API (`src.models`)

::: src.models
    options:
      show_root_heading: true
      show_source: true
      members_order: source
