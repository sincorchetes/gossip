# Visión General de Proveedores

El paquete `src.providers` encapsula toda la interacción con los backends de gestión de secretos. Cada proveedor hereda de [`BaseSecretProvider`](base.md) y traduce las llamadas a SDKs y excepciones externas a estructuras limpias del dominio.

---

## Matriz Comparativa de Características

| Característica | GCP | AWS Secrets Manager | AWS Parameter Store | Azure Key Vault | Ansible Vault | HashiCorp Vault / OpenBao | Kubernetes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Identificador** | `"gcp"` | `"aws"` | `"ssm"` | `"azure"` | `"ansible"` | `"vault"` | `"k8s"` |
| **Cliente** | `google-cloud-secret-manager` | `boto3` | `boto3` | `azure-keyvault-secrets` | `ansible-vault` y `PyYAML` | Biblioteca estándar (HTTP) | Biblioteca estándar (HTTP) y `PyYAML` |
| **Autenticación** | ADC, `gcloud`, cuenta de servicio | Cadena de credenciales AWS, perfiles, SSO | Cadena de credenciales AWS, perfiles, SSO | `DefaultAzureCredential`, CLI | Contraseña escrita o `.vault_pass` privado | Token (`VAULT_TOKEN`, `~/.vault-token`, escrito) | kubeconfig: token, certificado, plugin `exec` |
| **Contexto** | ID de proyecto | Perfil y región | Perfil y región | Nombre / URL del Key Vault | Ruta del archivo | Servidor, montaje KV v2, namespace | Contexto y namespace |
| **Historial de versiones** | ✅ | ✅ (etiquetas de estado) | ✅ (etiquetas) | ✅ | ✅ últimos 5 guardados | ✅ | ➖ una sola versión |
| **Deshabilitar / habilitar versión** | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ borrado lógico / restaurar | ❌ |
| **Destruir versión** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Etiquetas / tags** | ✅ labels | ✅ tags | ✅ tags | ✅ tags | ❌ (variables YAML) | ✅ metadatos personalizados al crear | ✅ labels |
| **Valores con varias claves** | ❌ | ❌ | ❌ | ❌ | ✅ YAML con tipos | ✅ JSON ↔ claves | ✅ JSON ↔ claves |
| **Comportamiento al borrar** | Irreversible | Recuperable 7 días (o inmediato) | Irreversible | Borrado lógico del servicio | Irreversible (copias conservadas) | Metadatos y todas las versiones | Irreversible |
| **Editar etiquetas / descripción** | ✅ labels | ✅ tags + descripción | ✅ tags | ✅ tags + tipo de contenido | ❌ | ✅ metadatos personalizados | ✅ labels |
| **Restaurar una versión anterior** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ (sin historial) |
| **Crear nunca sobrescribe** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ check-and-set | ✅ |
| **Diálogo de contexto** | Lista de proyectos con búsqueda | Perfil y región | Perfil y región | Nombre del vault + vaults descubiertos | Explorador de archivos y desbloqueo | Dirección, montaje, namespace, token | Lista de contextos y namespaces |

Todos los proveedores traducen los fallos a las [excepciones del dominio](../api/exceptions.md), que además heredan de las excepciones integradas correspondientes (`PermissionError`, `FileNotFoundError`, `ValueError`, `RuntimeError`). AWS y Azure usan tiempos de espera de conexión y lectura con dos reintentos, e informan con un mensaje claro cuando el servidor no es alcanzable.

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
    VaultClient,
    SSMClient,
    KubernetesClient,
)
```

Cada proveedor implementa además dos ganchos opcionales que usa la interfaz: `saved_context()` / `restore_context()` (las selecciones no sensibles que se recuerdan entre ejecuciones) y `lock()` (olvidar el material secreto en memoria por inactividad).
