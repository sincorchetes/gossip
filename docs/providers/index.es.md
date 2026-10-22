# Visión General de Proveedores

El paquete `src.providers` encapsula toda la interacción con los backends de gestión de secretos. Cada proveedor hereda de [`BaseSecretProvider`](base.md) y traduce las llamadas a SDKs y excepciones externas a estructuras limpias del dominio.

---

## Matriz Comparativa de Características

| Característica | Google Cloud (GCP) | Amazon Web Services (AWS) | Microsoft Azure (Key Vault) | Ansible Vault |
| :--- | :---: | :---: | :---: | :---: |
| **Identificador** | `"gcp"` | `"aws"` | `"azure"` | `"ansible"` |
| **SDK Subyacente** | `google-cloud-secret-manager` | `boto3` | `azure-keyvault-secrets` | `ansible-vault` & `PyYAML` |
| **Autenticación** | ADC, `gcloud`, Service Account | Credenciales AWS, Perfiles, SSO | DefaultAzureCredential, CLI | Contraseña directa, `.vault_pass` |
| **Identificador de Contexto** | ID de Proyecto GCP | Perfil y Región AWS | Nombre / URL de Key Vault | Ruta del Archivo Vault |
| **Alternar Versiones** | ✅ `ENABLED` / `DISABLED` | ❌ No soportado | ✅ `ENABLED` / `DISABLED` | ❌ No soportado |
| **Destrucción de Versiones** | ✅ Purga permanente de carga | ❌ No soportado | ❌ No soportado | ❌ No soportado |
| **Etiquetas / Tags** | ✅ Diccionario de labels | ✅ Diccionario de tags | ✅ Diccionario de tags | ❌ N/A (Variables YAML) |
| **Diálogo de Contexto** | Diálogo con búsqueda de proyectos | Diálogo de selección de perfil y región | Diálogo de selección de almacén | Explorador de archivos y desbloqueo |

---

## Exportaciones Públicas

El paquete `src.providers` proporciona un único punto de entrada unificado:

```python
from src.providers import (
    BaseSecretProvider,
    GCPSecretClient,
    AWSSecretClient,
    AzureSecretClient,
    AnsibleVaultClient,
)
```
