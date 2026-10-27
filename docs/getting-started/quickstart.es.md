# Guía Rápida y Configuración de Proveedores

Aprende a autenticarte con cada backend de secretos soportado, a configurar entornos y a usar las opciones de línea de comandos.

---

## Configuración de autenticación por proveedor

Gossip se conecta directamente a las API de los proveedores y a archivos locales con credenciales estándar. Configura el proveedor que necesites antes de lanzarlo, o cambia su contexto desde la barra de cabecera cuando Gossip esté en marcha.

### 1. Google Cloud Platform (GCP Secret Manager)

Gossip usa las Application Default Credentials (ADC) de Google:

1. **Inicia sesión con la CLI de Google Cloud:**
   ```bash
   gcloud auth application-default login
   ```
2. **Define tu proyecto activo:**
   ```bash
   gcloud config set project TU_ID_DE_PROYECTO
   ```
   *Alternativamente, usa un archivo de clave de cuenta de servicio:*
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/ruta/a/service-account.json"
   ```
3. **Permisos IAM necesarios:**
   * `roles/secretmanager.secretAccessor` (leer valores)
   * `roles/secretmanager.viewer` (listar secretos y versiones)
   * `roles/secretmanager.admin` (crear, borrar y gestionar secretos)

---

### 2. Amazon Web Services (AWS Secrets Manager)

Gossip usa la cadena de credenciales estándar de AWS:

1. **Configura las credenciales:**
   ```bash
   aws configure
   ```
   *O define variables de entorno:*
   ```bash
   export AWS_ACCESS_KEY_ID="AKIA..."
   export AWS_SECRET_ACCESS_KEY="..."
   export AWS_DEFAULT_REGION="eu-west-1"
   ```
2. **Perfiles con nombre** de `~/.aws/credentials` y `~/.aws/config`:
   ```bash
   gossip --provider aws --aws-profile production --aws-region us-east-1
   ```
3. **Acciones IAM necesarias:**
   * `secretsmanager:ListSecrets`, `DescribeSecret`, `GetSecretValue`, `ListSecretVersionIds`
   * `CreateSecret`, `PutSecretValue`, `DeleteSecret` para modificar datos

> [!NOTE]
> Borrar un secreto lo programa para eliminarse con una **ventana de recuperación de 7 días**. El diálogo de borrado tiene una casilla para eliminarlo de inmediato. Los secretos binarios se muestran como `base64:<datos>` y se guardan de vuelta como bytes.

---

### 3. AWS Systems Manager Parameter Store

Usa el mismo perfil, región y credenciales que Secrets Manager:

```bash
gossip --provider ssm --aws-profile production --aws-region eu-west-1
```

* Los parámetros se listan con su ruta completa (`/app/prod/db`) y su tipo.
* Los parámetros nuevos se crean como `SecureString` cifrado. Editar conserva el tipo y crea una versión nueva; el historial muestra las etiquetas.
* **Acciones IAM necesarias:** `ssm:DescribeParameters`, `ssm:GetParameter`, `ssm:GetParameterHistory`, `ssm:PutParameter`, `ssm:DeleteParameter` (y `kms:Decrypt` con claves propias).

---

### 4. Microsoft Azure Key Vault

Gossip se autentica con `DefaultAzureCredential`:

1. **Inicia sesión:**
   ```bash
   az login
   ```
   *O usa variables de un Service Principal:*
   ```bash
   export AZURE_CLIENT_ID="..."
   export AZURE_CLIENT_SECRET="..."
   export AZURE_TENANT_ID="..."
   ```
2. **Elige el vault** en el diálogo de Gossip (se listan los vaults que encuentra la CLI de Azure, o se te explica por qué no pudo), con `--azure-vault`, o mediante el entorno:
   ```bash
   export AZURE_KEYVAULT_NAME="mi-vault-de-produccion"
   ```
3. **Roles RBAC necesarios:** `Key Vault Secrets User` (leer) y `Key Vault Secrets Officer` (crear, actualizar, habilitar/deshabilitar y borrar).

---

### 5. Ansible Vault (archivos locales)

Explora, actualiza y añade variables de archivos YAML cifrados con Ansible Vault:

1. **Archivos descubiertos:** `vault.yml`, `vault.yaml`, `group_vars/all/vault.yml`, `vars/vault.yml`, `secrets.yml`, `.vault.yml`, y cualquier archivo que empiece con la firma `$ANSIBLE_VAULT`.
2. **Contraseña:**
   * Escríbela en el diálogo de desbloqueo de Gossip (se vuelve a pedir tras el bloqueo por inactividad), o
   * indica un archivo de contraseña con `--ansible-password-file` o:
     ```bash
     export ANSIBLE_VAULT_PASSWORD_FILE="/ruta/a/.vault_pass"
     ```
     El archivo debe ser privado (`chmod 600`); Gossip ignora los archivos de contraseña legibles por otros usuarios y nunca los busca por su cuenta. La contraseña no se lee de variables de entorno.
3. **Historial:** cada guardado conserva las últimas cinco generaciones como copias junto al archivo (`.bak`, `.bak.2` … `.bak.5`).

---

### 6. HashiCorp Vault y OpenBao

Ambos se soportan mediante el motor de secretos **KV versión 2**:

```bash
export VAULT_ADDR="https://vault.example.com:8200"   # o BAO_ADDR
vault login                                          # escribe ~/.vault-token
gossip --provider vault --vault-mount secret
```

* **Token**: `VAULT_TOKEN` / `BAO_TOKEN`, luego `~/.vault-token`, o escríbelo en el diálogo del servidor (solo en memoria y se descarta con el bloqueo por inactividad).
* **Namespace** con `VAULT_NAMESPACE` / `BAO_NAMESPACE`; **CA propia** con `VAULT_CACERT` / `BAO_CACERT`.
* `http://` solo se acepta para `localhost`; los certificados siempre se verifican.
* Un objeto JSON se guarda como varias claves, otro texto bajo la clave `value`. Las versiones se pueden deshabilitar (borrado lógico), rehabilitar y destruir.
* **La política** necesita `read`, `list`, `create`, `update` y `delete` sobre `<montaje>/data/*` y `<montaje>/metadata/*`, y `update` sobre `<montaje>/delete/*`, `<montaje>/undelete/*` y `<montaje>/destroy/*` para las acciones sobre versiones.

---

### 7. Kubernetes Secrets

Gossip lee tu kubeconfig (`KUBECONFIG`, o `~/.kube/config`) y gestiona los Secrets de un namespace:

```bash
gossip --provider k8s --kube-context mi-cluster --kube-namespace apps
```

* El diálogo lista tus contextos y los namespaces del clúster elegido (escribe el nombre si no puedes listar namespaces).
* Autenticación: token, certificado de cliente o plugins de credenciales `exec` (EKS, GKE, AKS, OIDC). Se rechazan los contextos con `insecure-skip-tls-verify` y los métodos antiguos `auth-provider` o autenticación básica.
* Un objeto JSON de cadenas se guarda como varias claves; los valores binarios aparecen como `base64:<datos>`. Editar conserva el tipo y las etiquetas del Secret. Cada Secret tiene una versión.
* **RBAC** necesita `get`, `list`, `create`, `update` y `delete` sobre `secrets` en el namespace.

---

## Contexto recordado

Gossip recuerda el último proveedor y contexto (proyecto, perfil y región, vault, ruta del archivo de Ansible, servidor y montaje, contexto y namespace de Kubernetes) y los restaura la próxima vez. Precedencia: **línea de comandos**, luego **lo guardado** y luego la autodetección. Las contraseñas y los tokens nunca se guardan. Consulta [Seguridad y Privacidad](../security.md).

---

## Interfaz de línea de comandos (CLI)

```bash
gossip [OPCIONES]
```

### Proveedores y contextos

| Argumento | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `-P`, `--provider` | Proveedor inicial: `gcp`, `aws`, `ssm`, `azure`, `ansible`, `vault`, `k8s` (por defecto: el último usado, si no `gcp`) | `--provider vault` |
| `-p`, `--project` | ID del proyecto de GCP | `--project mi-app-prod` |
| `--aws-profile` | Perfil de credenciales de AWS (AWS y Parameter Store) | `--aws-profile prod-team` |
| `--aws-region` | Región de AWS (AWS y Parameter Store) | `--aws-region us-east-1` |
| `--azure-vault` | Nombre o URL del Key Vault de Azure | `--azure-vault prod-keyvault` |
| `--ansible-vault` | Ruta del archivo de Ansible Vault | `--ansible-vault ./vault.yml` |
| `--ansible-password-file` | Archivo de contraseña (debe ser `chmod 600`) | `--ansible-password-file ./.pass` |
| `--vault-addr` | URL del servidor HashiCorp Vault / OpenBao (por defecto: `VAULT_ADDR`) | `--vault-addr https://vault.example.com:8200` |
| `--vault-mount` | Ruta de montaje KV v2 (por defecto: `secret`) | `--vault-mount kv` |
| `--kube-context` | Contexto del kubeconfig (por defecto: el actual) | `--kube-context prod` |
| `--kube-namespace` | Namespace cuyos Secrets gestionar | `--kube-namespace apps` |

### Seguridad y diagnóstico

| Argumento | Descripción |
| :--- | :--- |
| `--read-only` | Solo consultar y copiar; bloqueado durante toda la sesión (también `GOSSIP_READ_ONLY=1`, que se puede alternar) |
| `--audit-log [ARCHIVO]` | Registra lo que se revela, copia y cambia (nunca valores). También `GOSSIP_AUDIT_LOG` |
| `--stale-days DÍAS` | Marca los secretos sin cambios durante tantos días (por defecto 90; `0` lo desactiva). También `GOSSIP_STALE_DAYS` |
| `--idle-lock SEGUNDOS` | Tiempo del bloqueo por inactividad (por defecto 300; `0` lo desactiva). También `GOSSIP_IDLE_LOCK_SECONDS` |
| `--debug` | Diagnóstico detallado por stderr (también `GOSSIP_DEBUG=1`) |
| `--self-test` | Comprueba que todas las dependencias cargan y termina |

### Ventana e idioma

| Argumento | Descripción |
| :--- | :--- |
| `-l`, `--lang` | Idioma de la interfaz: `en` o `es` |
| `-m`, `--maximized` | Iniciar maximizada |
| `--width`, `--height` | Tamaño inicial de la ventana en píxeles (por defecto: el último usado, si no 1280 × 820) |
| `--renderer` | Renderizador de GTK: `ngl`, `gl`, `vulkan`, `cairo` |
| `--software-rendering` | Fuerza el renderizado Cairo (máquinas virtuales, controladores sin 3D) |
| `-v`, `--version` | Muestra la versión y termina |
| `-h`, `--help` | Muestra la ayuda y termina |

### Ejemplos

```bash
gossip -P aws --aws-profile prod --aws-region eu-west-1
gossip -P vault --vault-addr https://bao.example.com:8200 --vault-mount kv
gossip -P k8s --kube-context staging --kube-namespace payments
gossip --read-only --audit-log          # consulta segura con un registro de auditoría local
```
