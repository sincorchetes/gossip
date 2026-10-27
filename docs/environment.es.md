# Variables de Entorno

Gossip lee unas pocas variables propias y, para cada proveedor, las variables que ya usan sus herramientas. Lo que pases por línea de comandos prevalece sobre el entorno, y el entorno prevalece sobre lo que Gossip recordó de la última sesión.

!!! note "Lo que nunca se lee del entorno"
    La **contraseña** de Ansible Vault siempre se escribe en el diálogo. Gossip no la lee de ninguna variable, y `ANSIBLE_VAULT_PASSWORD_FILE` solo indica un archivo (ver abajo). Las credenciales nunca se escriben en el archivo de estado.

## Gossip

| Variable | Opción equivalente | Efecto |
|---|---|---|
| `GOSSIP_DEBUG` | `--debug` | Cualquier valor no vacío escribe diagnósticos con datos sensibles ocultos en stderr. |
| `GOSSIP_READ_ONLY` | `--read-only` | `1` oculta y bloquea crear, editar y eliminar. La ventana ofrece un interruptor. |
| `GOSSIP_READ_ONLY_LOCKED` | la fija `--read-only` | `1` quita el interruptor, así que el modo solo lectura no se puede desactivar desde la ventana. |
| `GOSSIP_AUDIT_LOG` | `--audit-log ARCHIVO` | Añade una línea JSON por cada revelado, copia, creación, cambio y eliminación. Nunca se registran los valores. |
| `GOSSIP_STALE_DAYS` | `--stale-days N` | Días a partir de los cuales un secreto se marca como antiguo. Por defecto `90`; `0` desactiva la marca. |
| `GOSSIP_IDLE_LOCK_SECONDS` | `--idle-lock N` | Segundos de inactividad antes de bloquear la ventana. Por defecto `300`; `0` lo desactiva. |
| `GOSSIP_REVEAL_SECONDS` | `--reveal-timeout N` | Segundos que un valor revelado sigue visible antes de ocultarse y borrarse de la memoria. Por defecto `120`; `0` lo mantiene hasta que lo ocultes. |
| `GOSSIP_HIDE_ON_BLUR` | `--hide-on-blur` | `1` oculta un valor revelado en cuanto la ventana pierde el foco. Desactivado por defecto. |
| `GOSSIP_STATE_FILE` | — | Ruta completa de `state.json`, en lugar de la predeterminada de la plataforma. |
| `GOSSIP_SELFTEST_HEADLESS` | — | `1` permite que `--self-test` funcione sin pantalla (lo usa la CI). |

## Google Cloud (GCP)

| Variable | Uso |
|---|---|
| `GOOGLE_CLOUD_PROJECT`, `GCLOUD_PROJECT`, `CLOUDSDK_CORE_PROJECT` | Proyecto preseleccionado al arrancar, comprobadas en este orden. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Archivo de clave de cuenta de servicio o de cuenta externa para las credenciales predeterminadas de la aplicación. |
| `CLOUDSDK_CONFIG` | Carpeta de configuración de gcloud alternativa (donde `gcloud auth application-default login` guarda sus credenciales). |

Las credenciales salen de `google.auth.default()`, por lo que sirven `gcloud auth application-default login`, una cuenta de servicio o Workload Identity.

## AWS (Secrets Manager y Parameter Store)

| Variable | Uso |
|---|---|
| `AWS_PROFILE`, `AWS_DEFAULT_PROFILE` | Perfil preseleccionado al arrancar. |
| `AWS_REGION`, `AWS_DEFAULT_REGION` | Región preseleccionada al arrancar. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | Credenciales estáticas o temporales, leídas por boto3. |
| `AWS_SHARED_CREDENTIALS_FILE`, `AWS_CONFIG_FILE` | Ubicaciones alternativas de `~/.aws/credentials` y `~/.aws/config` (incluidos los perfiles SSO). |
| `AWS_CA_BUNDLE` | Paquete de CA propio para los endpoints de AWS (proxies corporativos). |
| `AWS_ENDPOINT_URL` | Endpoint personalizado, por ejemplo un endpoint de VPC. |

Los dos proveedores de AWS comparten perfil y región. Los tiempos de conexión y lectura están fijados en el cliente, de modo que una red colgada aparece como error en vez de congelar la ventana.

## Azure Key Vault

| Variable | Uso |
|---|---|
| `AZURE_KEYVAULT_NAME`, `AZURE_VAULT_NAME`, `AZURE_VAULT_URL`, `KEYVAULT_NAME` | Vault preseleccionado al arrancar, comprobadas en este orden. |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET` | Inicio de sesión con service principal, leídas por `DefaultAzureCredential`. |
| `AZURE_CLIENT_CERTIFICATE_PATH` | Service principal con certificado. |
| `AZURE_USERNAME`, `AZURE_PASSWORD` | Inicio de sesión con usuario y contraseña (no recomendado; mejor `az login`). |
| `AZURE_CONFIG_DIR` | Carpeta de configuración alternativa de Azure CLI. |

`DefaultAzureCredential` prueba, por este orden, el entorno, la identidad administrada y la sesión de Azure CLI.

## Ansible Vault

| Variable | Uso |
|---|---|
| `ANSIBLE_VAULT_FILE` | Archivo vault que se abre al arrancar. |
| `ANSIBLE_VAULT_PASSWORD_FILE` | Archivo de contraseña que se ofrece en el diálogo. Es la única fuente que Gossip respeta; nunca adivina archivos tipo `.vault_pass`. |

## HashiCorp Vault / OpenBao

Se aceptan ambos prefijos; `VAULT_*` se comprueba antes que `BAO_*`.

| Variable | Uso |
|---|---|
| `VAULT_ADDR`, `BAO_ADDR` | Dirección del servidor. Debe ser `https://`; `http://` solo se acepta para localhost. |
| `VAULT_TOKEN`, `BAO_TOKEN` | Token que se ofrece en el diálogo. Sin él se usa el token guardado por `vault login` (`~/.vault-token`). |
| `VAULT_NAMESPACE`, `BAO_NAMESPACE` | Namespace (Vault Enterprise y OpenBao). |
| `VAULT_CACERT`, `BAO_CACERT` | Paquete de CA para un servidor con certificado privado. Los certificados siempre se verifican. |

## Kubernetes

| Variable | Uso |
|---|---|
| `KUBECONFIG` | Lista de archivos kubeconfig separados por `:` (`;` en Windows). Por defecto `~/.kube/config`. |

Los clústeres que autentican con un plugin `exec` (`aws eks get-token`, `gke-gcloud-auth-plugin`, `kubelogin`) ejecutan ese comando con tu entorno, así que se aplican las variables de la herramienta correspondiente.

## Proxies y certificados

Los clientes HTTP respetan las variables habituales `HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY`, `SSL_CERT_FILE` y `REQUESTS_CA_BUNDLE`. Gossip no tiene ninguna opción para saltarse la verificación de certificados.

## Pantalla y plataforma

| Variable | Uso |
|---|---|
| `GSK_RENDERER` | Renderizador de GTK (`ngl`, `gl`, `vulkan`, `cairo`). `--renderer` lo fija; `--software-rendering` fuerza `cairo` y `LIBGL_ALWAYS_SOFTWARE=1`. |
| `LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG` | Idioma de la interfaz cuando no se ha elegido ninguno (en este orden); la elección hecha en el menú se recuerda después. |
| `XDG_CONFIG_HOME` | Base en Linux de la carpeta de estado (`~/.config` por defecto). |
| `APPDATA` | Base en Windows de la carpeta de estado. |

Los paquetes también fijan por sí mismos `GI_TYPELIB_PATH`, `GSETTINGS_SCHEMA_DIR`, `GDK_PIXBUF_MODULE_FILE`, `XDG_DATA_DIRS` y, en macOS, `DYLD_FALLBACK_LIBRARY_PATH`. No deberías necesitar tocarlas.

## Flatpak

El sandbox expone tus carpetas de credenciales en solo lectura (`~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.kube`, `~/.vault-token`) pero **no** el entorno de tu shell. Pasa las variables con `--env`, o de forma persistente con un override:

```bash
flatpak run --env=AWS_PROFILE=prod --env=VAULT_ADDR=https://vault.example.com \
    com.github.sincorchetes.gossip_gcp
flatpak override --user --env=AWS_PROFILE=prod com.github.sincorchetes.gossip_gcp
```

Dentro del sandbox el archivo de estado está en `~/.var/app/com.github.sincorchetes.gossip_gcp/config/gossip/state.json`. Los archivos fuera de esas carpetas (un vault de Ansible, un paquete de CA privado) necesitan `flatpak override --user --filesystem=<ruta>:ro`.
