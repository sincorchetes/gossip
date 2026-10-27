# Seguridad y Privacidad

Qué conserva Gossip, dónde lo conserva y qué se niega a hacer.

---

## Valores de los secretos

* Los valores se **obtienen solo cuando los revelas o los copias**, nunca al seleccionar un secreto.
* Un valor revelado vive en memoria solo mientras se muestra. Ocultarlo, cambiar de secreto o el bloqueo por inactividad lo descartan, y también un temporizador: un valor revelado se oculta solo a los 120 segundos (`--reveal-timeout`) y, opcionalmente, en cuanto la ventana pierde el foco (`--hide-on-blur`).
* **Copiar** coloca el valor en el portapapeles y lo borra a los **30 segundos** (solo si el portapapeles sigue conteniendo lo que puso Gossip). El bloqueo por inactividad también lo borra.
* El valor copiado también se **marca como sensible** (`x-kde-passwordManagerHint`, `org.nspasteboard.ConcealedType` y las exclusiones del historial del portapapeles de Windows), de modo que los gestores de portapapeles y la sincronización en la nube que respetan esas señales no lo guardan. Son convenciones de mejor esfuerzo: una herramienta que las ignore sigue recibiendo el texto, por eso existe el borrado automático.
* El diff de versiones muestra texto en claro y se descarta al cerrar su ventana.
* Las exportaciones contienen valores solo si marcas *Incluir los valores*; el archivo se crea legible solo por ti (`0600`).

## Bloqueo por inactividad y de sesión

En Linux y BSD Gossip además se bloquea **en cuanto se bloquea la pantalla o el equipo se suspende** (escucha a `logind` y al salvapantallas de GNOME / freedesktop por D-Bus). macOS y Windows solo usan el temporizador.

Tras 5 minutos sin actividad (`--idle-lock SEGUNDOS`, `GOSSIP_IDLE_LOCK_SECONDS`, `0` lo desactiva) Gossip oculta y olvida el valor, cierra el diff, vacía el portapapeles, descarta el token de HashiCorp Vault que escribiste y bloquea el vault de Ansible.

## Credenciales

| Proveedor | Cómo se obtienen las credenciales | Qué guarda Gossip |
|---|---|---|
| GCP | Application Default Credentials | Nada |
| AWS / Parameter Store | Cadena de credenciales estándar de AWS y perfiles | Nada |
| Azure | `DefaultAzureCredential` | Nada |
| Ansible Vault | Contraseña escrita cada vez, o un archivo de contraseña privado | Nada. La contraseña nunca se lee del entorno y los archivos de contraseña nunca se adivinan; un archivo legible por otros usuarios se ignora |
| HashiCorp Vault / OpenBao | Token escrito en el diálogo (solo en memoria), `VAULT_TOKEN` / `BAO_TOKEN` o `~/.vault-token` | Nada |
| Kubernetes | Tu kubeconfig (token, certificado o plugin `exec`) | Nada |

## Reglas de red

* Los certificados **siempre se verifican**. No hay opción para desactivar la verificación: los contextos de Kubernetes con `insecure-skip-tls-verify` se rechazan y Vault no tiene un interruptor equivalente. Usa una CA propia en su lugar (`VAULT_CACERT`, o la `certificate-authority` del clúster).
* El token de Vault viaja en una cabecera, por eso se rechazan las direcciones `http://` salvo `localhost`.
* Las conexiones agotan el tiempo en pocos segundos (AWS y Azure reintentan dos veces) y muestran un mensaje claro en lugar de esperar indefinidamente.

## Qué se recuerda entre ejecuciones

Gossip guarda tu último proveedor y contexto para que no tengas que elegirlos otra vez. El archivo es `state.json` en la carpeta de configuración, legible solo por ti:

| Plataforma | Ubicación |
|---|---|
| Linux | `$XDG_CONFIG_HOME/gossip/` o `~/.config/gossip/` |
| macOS | `~/Library/Application Support/gossip/` |
| Windows | `%APPDATA%\gossip\` |

Contiene nombres como el proyecto de GCP, el perfil y región de AWS, el vault de Azure, la **ruta** del archivo de Ansible, la dirección / montaje / namespace de Vault y el contexto / namespace de Kubernetes. **Nunca se guardan contraseñas, tokens ni claves**: todo lo que por su nombre parezca una credencial se descarta antes de escribir. El archivo también guarda los cinco contextos más recientes de cada proveedor (los usa *Comparar con otro secreto*) y tus preferencias de interfaz (tema, idioma, tamaño de la ventana). Borra el archivo para olvidarlo todo. Dentro del sandbox de Flatpak la carpeta es `~/.var/app/com.github.sincorchetes.gossip_gcp/config/gossip/`. La precedencia al arrancar es: opción de línea de comandos, luego lo guardado y luego la autodetección (entorno, herramientas de línea de comandos, kubeconfig).

## Modo de solo lectura

El candado de la cabecera (o `--read-only`, `GOSSIP_READ_ONLY=1`) oculta todos los controles que modifican datos y bloquea las acciones subyacentes. `--read-only` bloquea el modo durante la sesión. Protege de errores en la interfaz; tus credenciales siguen definiendo lo que permite el proveedor.

## Registro de auditoría

`--audit-log [ARCHIVO]` (o `GOSSIP_AUDIT_LOG`) registra los eventos de revelar, copiar, crear, cambiar, borrar, importar y exportar como líneas JSON en un archivo privado. Guarda nombres, contadores y versiones, **nunca valores**. Úsalo junto con una identidad de solo lectura cuando necesites demostrar a qué se accedió.

## Seguridad al borrar

* Los borrados de AWS Secrets Manager son **recuperables durante 7 días** salvo que marques *Eliminar de inmediato*.
* Crear nunca sobrescribe un secreto existente, en ningún proveedor.
* Importar nunca sobrescribe secretos existentes.
* Ansible Vault conserva las últimas cinco copias al guardar junto al archivo.

## Informe de diagnóstico

La sección *Solución de problemas* de la ventana Acerca de ofrece un informe para los informes de errores. Lista versiones y ajustes y las últimas líneas de depuración sin credenciales, URL con contraseña ni tu carpeta personal. Nunca contiene proyectos, vaults, servidores, nombres de secretos ni valores.

---

## Publicaciones y cadena de suministro

* Todas las dependencias están fijadas con hashes (`--require-hashes`) y las GitHub Actions están fijadas por commit.
* Una **auditoría de dependencias** semanal (`pip-audit`, y también en cada cambio de los ficheros de bloqueo) revisa las versiones fijadas en busca de vulnerabilidades conocidas, y cada publicación incluye un **SBOM CycloneDX** de las dependencias de Python (`gossip-python-sbom-*.cdx.json`).
* Cada publicación incluye un `SHA256SUMS.txt` y una atestación firmada de procedencia de la compilación. Verifica una descarga con `sha256sum -c SHA256SUMS.txt` o `gh attestation verify <archivo> -R sincorchetes/gossip`.
* Las licencias de terceros están en `THIRD_PARTY_NOTICES.md` y en el diálogo Acerca de. Gossip se distribuye bajo GPL-3.0-or-later.
* `gossip --self-test` verifica que todas las dependencias incluidas cargan y que el cifrado funciona.
