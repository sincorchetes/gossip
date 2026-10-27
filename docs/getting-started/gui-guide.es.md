# Guía de la Interfaz Gráfica (GUI)

**Gossip** ofrece un diseño nativo de GNOME construido según las **Directrices de Interfaz Humana de GNOME (HIG)** con **Libadwaita** y **GTK4**.

---

## 1. Controles de la barra de cabecera

La barra superior reúne los controles globales, el selector de contexto y los indicadores de estado:

```text
[ Proveedor ▾ ] [ Contexto ] [ ⟳ ] [ Importar/Exportar ] [ 🔒 Solo lectura ] ---- Gossip (subtítulo) ---- [ ☀/☾ ] [ ES / EN ] [ ℹ ]
```

* **Desplegable de proveedor**:
  Cambia en caliente entre **Google Cloud (GCP)**, **AWS Secrets Manager**, **AWS Parameter Store**, **Azure Key Vault**, **Ansible Vault**, **HashiCorp Vault / OpenBao** y **Kubernetes Secrets**. Gossip recuerda el último que usaste (consulta [Seguridad y Privacidad](../security.md)).
* **Botón de contexto**:
  Se adapta al backend activo. El subtítulo de la ventana siempre muestra qué estás viendo.

  | Proveedor | Contexto mostrado | El botón abre |
  |---|---|---|
  | GCP | ID del proyecto | Diálogo de búsqueda y cambio de proyecto |
  | AWS / Parameter Store | `perfil (región)` | Diálogo de perfil y región |
  | Azure | Nombre del Key Vault | Diálogo del vault, con los vaults que encuentra la CLI de Azure (o el motivo de que no pudiera listarlos) |
  | Ansible Vault | Nombre del archivo | Diálogo de archivo y contraseña |
  | HashiCorp Vault / OpenBao | `servidor (montaje)` | Dirección del servidor, montaje KV v2, namespace y token |
  | Kubernetes | `contexto / namespace` | Contexto del kubeconfig y los namespaces de ese clúster |

* **Recargar (`⟳`)**: vuelve a consultar el proveedor en segundo plano sin congelar la ventana.
* **Menú Importar / Exportar**: consulta la sección 7. En modo de solo lectura solo se ofrece *Exportar*.
* **Interruptor de solo lectura (🔒)**: bloquea crear, editar y borrar. Consulta la sección 8.
* **Banner de notificaciones**: aparece si faltan credenciales o falla una conexión, con instrucciones para resolverlo. Los servidores inalcanzables agotan el tiempo en pocos segundos con un mensaje claro, en lugar de quedarse girando.
* **Tema (`☀/☾`)**: alterna entre modo claro y oscuro al instante.
* **Idioma (`ES / EN`)**: cambia etiquetas, tooltips y diálogos entre español e inglés.
* **Acerca de (`ℹ`)**: versión, autores, licencia, avisos de terceros y créditos.

---

## 2. Barra lateral (Navegación de secretos)

* **Búsqueda en vivo** (`Ctrl+F` —`Cmd+F` en macOS— para enfocarla, `Esc` para limpiarla): filtrado instantáneo, sin distinguir mayúsculas, por nombre, descripción y etiquetas. Varias palabras deben coincidir todas, y aparece un mensaje cuando no hay resultados.

  | Consulta | Muestra |
  |---|---|
  | `db password` | Secretos que contienen ambas palabras |
  | `label:env` | Secretos con una etiqueta `env` |
  | `label:env=prod` | Secretos cuya etiqueta `env` es exactamente `prod` |
  | `db -legacy` | Secretos que coinciden con `db` pero no con `legacy` |

* **Crear secreto (`+`)**: abre el diálogo de creación, adaptado al proveedor (oculto en modo de solo lectura):

  | Proveedor | Qué introduces |
  |---|---|
  | GCP | ID del secreto, contenido inicial, etiquetas |
  | AWS Secrets Manager | Nombre, descripción opcional, contenido, etiquetas |
  | AWS Parameter Store | Nombre del parámetro (p. ej. `/app/prod/db`), descripción opcional, valor, etiquetas. Se guarda como `SecureString` cifrado |
  | Azure | Nombre, tipo de contenido, contenido, etiquetas |
  | Ansible Vault | Nombre de la variable y valor (números, booleanos, listas y mapas conservan su tipo) |
  | HashiCorp Vault / OpenBao | Ruta del secreto y valor. Un objeto JSON se guarda como varias claves; cualquier otro texto, bajo la clave `value` |
  | Kubernetes | Nombre del Secret y claves. Un objeto JSON de cadenas se guarda como varias claves; cualquier otro texto, bajo `value` |

  Crear **nunca sobrescribe** un secreto existente en ningún proveedor: en su lugar verás "ya existe, usa Nueva versión".
* **Lista de secretos**: cada fila muestra el nombre, una descripción corta y la fecha. Al seleccionar uno se cargan sus metadatos y versiones. El valor solo se obtiene cuando lo revelas o lo copias.
  * **Vista de árbol**: los nombres con `/` (AWS, Parameter Store, Vault) se agrupan en carpetas que se abren y cierran con un clic y muestran cuántos secretos contienen. Las listas pequeñas empiezan desplegadas; las largas, plegadas. Mientras buscas, las coincidencias se listan planas con su nombre completo.
  * **Listas grandes**: la lista está virtualizada, así que miles de secretos siguen respondiendo con fluidez.
  * **Marca de antigüedad**: una píldora amarilla como `200 d` señala los secretos sin cambios desde hace 90 días o más (`--stale-days DÍAS` o `GOSSIP_STALE_DAYS` lo cambian; `0` lo desactiva). Usa la fecha de última modificación que informa el proveedor.

---

## 3. Panel de detalle (Inspección y gestión)

### Información general
* **Editar** (lápiz, oculto en modo de solo lectura): cambia las etiquetas (una `clave=valor` por línea) y, donde el proveedor lo permite, la descripción. Soportado por GCP, AWS Secrets Manager, Parameter Store (etiquetas), Azure, Vault / OpenBao y Kubernetes. El valor nunca se toca.
* **Nombre del recurso** con un botón de **Copiar**, **fecha de creación**, **replicación** (o *Montaje* / *Namespace* en Vault y Kubernetes) y **etiquetas**.

### Valor del secreto
* **Oculto por defecto** con puntos (`••••••••`), para que nada sensible se vea por encima del hombro.
* **Revelar (ojo)** lo muestra u oculta. Ocultarlo borra el valor de la memoria.
* **Copiar** lo pone en el portapapeles, que se vacía automáticamente a los 30 segundos.
* **Secretos con varias claves** (Vault, Kubernetes, Parameter Store con JSON) se muestran y editan como un objeto JSON. Una única clave `value` se muestra como texto plano.
* **Vista de tabla**: cuando el valor revelado es un objeto JSON, el botón de tabla muestra una fila por clave, cada una con su botón de copiar, para copiar solo `password` sin el resto.
* **Copiar** y **Copiar clave** colocan el valor en el portapapeles marcado como sensible, de modo que los gestores de portapapeles que lo respetan (KDE Klipper, KeePassXC, el historial de macOS y de Windows) no lo conservan.
* **Valores binarios**: los binarios de AWS Secrets Manager y las claves binarias de Kubernetes aparecen como `base64:<datos>` y se escriben de vuelta como los mismos bytes al guardar. GCP muestra un volcado hexadecimal.

### Historial de versiones
* **Línea de tiempo** con la más reciente primero. Insignias: `Habilitada`, `Deshabilitada`, `Destruida`, o las etiquetas del proveedor (`Actual`, `Anterior`, etiquetas de Parameter Store).
* **Acciones sobre versiones** (ocultas en modo de solo lectura):
  * *Deshabilitar / Habilitar*: GCP, Azure y HashiCorp Vault (borrado lógico y restauración).
  * *Destruir*: GCP y HashiCorp Vault, permanente e irreversible (con confirmación).
* **Según el proveedor**:
  * Ansible Vault conserva las últimas cinco copias al guardar y lista las generaciones en las que existía la variable.
  * Kubernetes no tiene historial: cada Secret tiene una versión (su `resourceVersion`).
* **Nueva versión** añade un valor nuevo sin cambiar el nombre ni la configuración del secreto. El botón generador de contraseñas (icono de llave) genera una contraseña aleatoria (longitud, tipos de caracteres y una opción para evitar caracteres que se parecen) y la pone en el cuadro de texto; también está disponible al crear un secreto.
* **Restaurar** (icono de deshacer en una versión anterior legible): guarda el valor de esa versión de nuevo como versión actual tras confirmar. No se pierde nada; el historial solo crece. Kubernetes no lo ofrece porque no guarda historial.

---

## 4. Borrar un secreto

1. Pulsa el botón destructivo **Borrar** en la vista de detalle.
2. Confirma en el diálogo.

Lo que ocurre depende del proveedor:

* **AWS Secrets Manager**: el secreto queda **programado para eliminarse y se puede restaurar durante 7 días**. Marca *Eliminar de inmediato, sin periodo de recuperación* en el diálogo para saltarte ese plazo.
* **Azure Key Vault**: borrado lógico por el servicio (el nombre queda reservado mientras sea recuperable).
* **Resto**: el secreto y todas sus versiones se eliminan y no se puede deshacer.

---

## 5. Comparar versiones

Cuando un secreto tiene dos o más versiones, **Comparar** abre una ventana de diferencias:

1. Elige las versiones *Desde* y *Hasta* (por defecto la anterior y la última).
2. Pulsa **Comparar**. Gossip obtiene ambos valores en segundo plano y muestra un diff unificado: líneas añadidas en verde y eliminadas en rojo.
3. Los valores JSON se normalizan (claves ordenadas, sangría), así que un cambio solo de formato no se reporta.

> [!WARNING]
> El diff muestra los valores en claro. Se descartan al cerrar la ventana o al saltar el bloqueo por inactividad.

---

## 5b. Comparar con otro secreto

El segundo botón de comparar (junto al primero) abre **Comparar con otro secreto**. Elige con qué comparar: cualquier proveedor en su contexto actual, o uno de los cinco contextos más recientes que usaste con ese proveedor (por ejemplo los proyectos *staging* y *prod*). Se listan los secretos de ese lugar con un filtro; elige uno y pulsa **Comparar** para ver el diff unificado frente al secreto actual. Ansible Vault solo se ofrece con su archivo actual, porque otro vault necesitaría su propia contraseña.

---

## 6. Bloqueo por inactividad

Tras 5 minutos sin teclado, ratón ni desplazamiento, Gossip oculta el valor revelado, lo elimina de la memoria, cierra cualquier ventana de diff, vacía el portapapeles si aún contiene un secreto copiado desde Gossip, descarta el token de HashiCorp Vault que hubieras escrito y **bloquea el vault de Ansible**. Al volver, los valores solo se obtienen de nuevo si los pides, y la contraseña de Ansible se solicita otra vez (o se relee de tu archivo de contraseña privado).

Lo mismo ocurre de inmediato cuando **se bloquea la pantalla o el equipo se suspende** (Linux y BSD, mediante D-Bus: GNOME, KDE y `logind`). En macOS y Windows solo se aplica el temporizador de inactividad.

Cambia el tiempo con `--idle-lock SEGUNDOS` o `GOSSIP_IDLE_LOCK_SECONDS` (`0` desactiva el temporizador).

---

## 7. Exportar e importar secretos

El menú **Importar / Exportar** traslada secretos entre entornos o guarda una copia.

* **Exportar secretos…** escribe un JSON con todos los secretos de la barra lateral (nombre, descripción y etiquetas). Los valores **no se incluyen** salvo que marques *Incluir los valores*; entonces el archivo los contiene en claro y se crea legible solo por ti (`0600`).
* **Importar secretos…** lee una exportación de Gossip, o un mapa JSON/YAML simple `{ "nombre": "valor" }`, y abre una **vista previa**: cuántos secretos son nuevos y cuántos ya existen, con una fila por entrada. Elige qué hacer con los que existen: **omitirlos** (conservar el valor actual) o **añadir el valor importado como nueva versión**. Los secretos existentes nunca se sobrescriben; un resumen indica qué se creó, qué recibió una versión nueva, qué se omitió y qué falló.
* Los secretos con varias claves (Vault, Kubernetes) viajan como texto JSON, así que puedes exportar de un proveedor e importar en otro.

```json
{
  "format": "gossip-export", "version": 1, "provider": "gcp",
  "secrets": [{ "id": "db_password", "labels": {"env": "prod"}, "value": "…" }]
}
```

> [!NOTE]
> Las exportaciones contienen la última versión de cada secreto. En Ansible Vault, los diccionarios, listas, números y booleanos se exportan como valores JSON nativos y se restauran con su tipo.

---

## 8. Modo de solo lectura

El **botón del candado** de la cabecera activa y desactiva el modo de solo lectura sin reiniciar:

* **Activado**: desaparecen los botones *Crear*, *Nueva versión* y *Borrar* y las acciones sobre versiones, *Importar* se quita del menú y el subtítulo añade "solo lectura". Cualquier acción de escritura que aún se dispare solo muestra un aviso y nunca llega al proveedor.
* **Desactivado**: todo vuelve a estar disponible.

Arranca en este modo con `gossip --read-only` o `GOSSIP_READ_ONLY=1`. Con **`--read-only` el modo queda bloqueado durante toda la sesión**: el botón se desactiva y no se puede apagar. Con solo la variable de entorno, el botón sigue siendo utilizable.

> [!NOTE]
> El modo de solo lectura protege la interfaz de errores. Tus credenciales siguen decidiendo lo que permite el proveedor, así que usa una identidad de solo lectura cuando necesites una garantía firme.

---

## 8b. Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+N` | Nuevo secreto |
| `Ctrl+F` | Buscar (`Cmd` en macOS) |
| `F5` / `Ctrl+R` | Recargar |
| `Ctrl+Shift+R` | Mostrar / ocultar el valor |
| `Ctrl+Shift+C` | Copiar el valor |
| `Ctrl+E` | Editar etiquetas y descripción |
| `Ctrl+Supr` | Borrar el secreto (con confirmación) |
| `F1` | Listar los atajos |

Los botones que solo tienen icono llevan nombres accesibles, para que los lectores de pantalla anuncien qué hacen. El tema, el idioma y el tamaño de la ventana se recuerdan entre sesiones.

---

## 9. Registro de auditoría

Inicia Gossip con `--audit-log [ARCHIVO]` (o `GOSSIP_AUDIT_LOG`) para conservar un registro local de lo que ocurre. Cada línea es un objeto JSON con la hora, el proveedor, el contexto, la acción y el nombre del secreto:

```json
{"time": "2026-10-26T10:15:02+00:00", "provider": "aws", "context": "AWS: prod (eu-west-1)", "action": "reveal", "secret": "prod/db"}
```

Acciones registradas: `reveal`, `copy`, `copy_key` (con el nombre de la clave), `create`, `add_version`, `restore_version`, `edit_metadata`, `enable_version`, `disable_version`, `destroy_version`, `delete`, `import` y `export`. **Nunca se escriben los valores**, y se descartan las claves que podrían contenerlos. Por defecto el archivo es `audit.jsonl` junto al estado guardado, privado para ti, y se rota a los 5 MB.

---

## 10. Diagnóstico para informes de errores

La ventana **Acerca de** tiene una sección *Solución de problemas* con un informe de diagnóstico que puedes copiar o guardar: versiones de Gossip, Python, GTK y las bibliotecas, la plataforma, los ajustes relevantes y las últimas 50 líneas de depuración. Las credenciales, los tokens, las URL con contraseña y tu carpeta personal se eliminan del registro, y el informe nunca incluye proyectos, vaults, servidores, nombres de secretos ni valores. Adjúntalo a una incidencia en lugar de describir tu entorno a mano.
