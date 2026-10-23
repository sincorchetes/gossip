# Guía Rápida y Configuración de Proveedores

Aprende a autenticarte con cada uno de los proveedores soportados, configurar credenciales y utilizar las opciones por línea de comandos.

---

## Configuración y Autenticación de Proveedores

Gossip se comunica de forma directa con las APIs oficiales y archivos locales utilizando credenciales estándar.

### 1. Google Cloud Platform (GCP Secret Manager)

Gossip emplea las credenciales predeterminadas de la aplicación (Application Default Credentials o ADC):

1. **Iniciar sesión con Google Cloud CLI:**
   ```bash
   gcloud auth application-default login
   ```
2. **Definir el proyecto activo:**
   ```bash
   gcloud config set project TU_PROJECT_ID
   ```
   *O utiliza una cuenta de servicio (Service Account):*
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/ruta/a/clave-sa.json"
   ```
3. **Roles y permisos IAM requeridos:**
   * `roles/secretmanager.secretAccessor` (leer valores de secretos)
   * `roles/secretmanager.viewer` (listar secretos y versiones)
   * `roles/secretmanager.admin` (crear, eliminar y gestionar secretos)

> [!TIP]
> Puedes cambiar de proyecto de Google Cloud en caliente en cualquier momento pulsando el botón de contexto en la barra superior.

---

### 2. Amazon Web Services (AWS Secrets Manager)

Gossip se integra con la cadena estándar de credenciales de AWS:

1. **Configurar credenciales con AWS CLI:**
   ```bash
   aws configure
   ```
   *O definir variables de entorno:*
   ```bash
   export AWS_ACCESS_KEY_ID="AKIA..."
   export AWS_SECRET_ACCESS_KEY="..."
   export AWS_DEFAULT_REGION="eu-west-1"
   ```
2. **Perfiles con nombre:**
   Soporta los perfiles configurados en `~/.aws/credentials` y `~/.aws/config`:
   ```bash
   gossip --provider aws --aws-profile produccion --aws-region us-east-1
   ```
3. **Políticas IAM recomendadas:**
   * `secretsmanager:ListSecrets`
   * `secretsmanager:DescribeSecret`
   * `secretsmanager:GetSecretValue`
   * `secretsmanager:CreateSecret`, `secretsmanager:PutSecretValue`, `secretsmanager:DeleteSecret`

---

### 3. Microsoft Azure Key Vault

Gossip se autentica contra Azure Key Vault mediante `DefaultAzureCredential`:

1. **Iniciar sesión en Azure CLI:**
   ```bash
   az login
   ```
   *O configurar variables de Service Principal:*
   ```bash
   export AZURE_CLIENT_ID="..."
   export AZURE_CLIENT_SECRET="..."
   export AZURE_TENANT_ID="..."
   ```
2. **Especificar el nombre del Key Vault:**
   Define la variable o indícalo en el selector de almacén de Gossip:
   ```bash
   export AZURE_KEYVAULT_NAME="mi-keyvault-prod"
   ```
3. **Roles RBAC requeridos:**
   * `Key Vault Secrets User` (lectura de secretos)
   * `Key Vault Secrets Officer` (creación, modificación, activación y eliminación)

---

### 4. Ansible Vault (Archivos Locales)

Gossip permite explorar y gestionar variables en archivos YAML cifrados con Ansible Vault sin necesidad de tener Ansible instalado en el sistema operativo:

1. **Convenciones de nombres detectadas automáticamente:**
   * `vault.yml`, `vault.yaml`
   * `group_vars/all/vault.yml`, `group_vars/all/vault.yaml`
   * `vars/vault.yml`, `secrets.yml`, `.vault.yml`
   * Cualquier archivo con la cabecera `$ANSIBLE_VAULT`.
2. **Configuración de Contraseña:**
   * Introduce la contraseña interactivamente en el diálogo de desbloqueo.
   * O selecciona un archivo de contraseña: `.vault_pass` en el proyecto o en `~/.vault_pass`.
   * O mediante variables de entorno:
     ```bash
     export ANSIBLE_VAULT_PASSWORD_FILE="/ruta/a/.vault_pass"
     export ANSIBLE_VAULT_PASSWORD="miPasswordSecreto"
     ```

---

## Opciones por Línea de Comandos (CLI)

Gossip admite parámetros para preseleccionar proveedor, contexto, idioma y dimensiones de ventana:

```bash
gossip [OPCIONES]
```

### Tabla de Parámetros

| Parámetro | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `--provider` | Proveedor activo (`gcp`, `aws`, `azure`, `ansible`) | `--provider aws` |
| `--gcp-project` | ID del proyecto de Google Cloud | `--gcp-project mi-proyecto` |
| `--aws-profile` | Perfil de credenciales de AWS | `--aws-profile equipo-prod` |
| `--aws-region` | Región destino de AWS | `--aws-region us-east-1` |
| `--azure-vault` | Nombre del almacén Azure Key Vault | `--azure-vault prod-keyvault` |
| `--ansible-vault` | Ruta al archivo de Ansible Vault | `--ansible-vault ./vault.yml` |
| `--ansible-password` | Contraseña en texto plano para el vault | `--ansible-password clave` |
| `--ansible-password-file` | Ruta al archivo `.vault_pass` | `--ansible-password-file ./.pass` |
| `--lang` | Idioma inicial de la interfaz (`es` o `en`) | `--lang es` |
| `--maximized` | Iniciar la ventana maximizada | `--maximized` |
| `--width` | Ancho de ventana en píxeles (mínimo: 900) | `--width 1440` |
| `--height` | Alto de ventana en píxeles (mínimo: 600) | `--height 900` |
| `--version` | Mostrar versión de Gossip y salir | `--version` |
| `--help` | Mostrar ayuda de comandos y salir | `--help` |
