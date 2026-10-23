# Guía de la Interfaz Gráfica (GUI)

**Gossip** cuenta con una interfaz gráfica nativa diseñada siguiendo rigurosamente las **GNOME Human Interface Guidelines (HIG)** mediante **Libadwaita** y **GTK4**.

---

## 1. Controles de la Barra Superior (Header Bar)

La barra de cabecera agrupa los selectores de contexto, filtros globales y opciones del sistema:

```text
[ Selector de Proveedor ▾ ]  [ Botón de Contexto ⚙ ]  [ ⟳ Recargar ]  ------ [ Gossip (Subtítulo) ] ------  [ ☀/☾ Tema ]  [ ES / EN ]  [ ℹ Acerca de ]
```

* **Selector Desplegable de Proveedor**:
  Permite alternar en caliente entre **Google Cloud (GCP)**, **Amazon Web Services (AWS)**, **Microsoft Azure (Key Vault)** y **Ansible Vault**. El cambio reemplaza la estrategia activa al instante de forma asíncrona sin bloquear la ventana.
* **Botón de Selección de Contexto**:
  Se adapta polimórficamente según el backend seleccionado:
  * En GCP: Muestra el Project ID actual; al pulsarlo abre el diálogo de búsqueda y cambio de proyectos.
  * En AWS: Muestra el perfil y región activos (`AWS: default (eu-west-1)`); abre el selector de perfiles y regiones.
  * En Azure: Muestra el nombre del Key Vault; abre el diálogo de configuración del almacén.
  * En Ansible Vault: Muestra el nombre del archivo YAML activo; abre el selector de archivo de vault y clave.
* **Botón de Recargar (`⟳`)**:
  Vuelve a consultar el backend de forma asíncrona y refresca los secretos en segundo plano.
* **Banner de Notificaciones**:
  Si faltan credenciales o se produce un error de conexión, se despliega automáticamente un `AdwBanner` con instrucciones exactas para autenticarte.
* **Alternar Tema (`☀/☾`)**:
  Cambia en tiempo real entre el tema claro y el modo oscuro.
* **Selector de Idioma (`ES / EN`)**:
  Traduce dinámicamente toda la interfaz (botones, tooltips, etiquetas y diálogos) entre español e inglés.
* **Botón Acerca de (`ℹ`)**:
  Muestra la ventana `Adw.AboutWindow` con información de versión, créditos, enlace al repositorio y seguimiento de incidencias.

---

## 2. Barra Lateral (Navegación de Secretos)

La barra lateral izquierda facilita la búsqueda, filtrado y creación de secretos:

* **Filtro de Búsqueda en Vivo**:
  Búsqueda insensible a mayúsculas/minúsculas instantánea por nombre o etiquetas.
* **Botón Crear Secreto (`+`)**:
  Abre el diálogo modal de creación:
  * Nombre / ID del secreto (validado según las reglas de cada proveedor).
  * Valor inicial (opcional; permite crear secretos vacíos).
  * Política de replicación (Automática o Multirregión para GCP).
  * Etiquetas (labels / tags) clave-valor.
* **Lista de Secretos**:
  Cada elemento muestra el nombre, fecha de creación y badges de estado. Al hacer clic se cargan sus detalles en el panel principal.

---

## 3. Panel de Detalle (Inspección y Gestión)

Al seleccionar un secreto, el panel derecho muestra tarjetas agrupadas con widgets de preferencias de Libadwaita:

### Tarjeta de Información General
* **Nombre de Recurso**: Identificador completo en la nube (ej. `projects/123/secrets/db_password` o ARN). Incluye un botón para **Copiar** al portapapeles.
* **Fecha de Creación**: Fecha y hora formateadas en la zona horaria local.
* **Replicación**: Tipo de replicación configurado (Automática o regiones específicas).
* **Etiquetas (Labels / Tags)**: Etiquetas clave-valor representadas en píldoras visuales.

### Tarjeta del Valor del Secreto (Payload)
* **Protección contra Miradas Ajenas**: El valor del secreto se enmascara por defecto con puntos (`••••••••`).
* **Botón Revelar (Icono de Ojo)**: Alterna entre el texto oculto y el texto en claro.
* **Botón Copiar**: Copia el secreto al portapapeles y muestra una notificación flotante (`Adw.Toast`).
* **Detección Automática de Binarios**: Si el valor contiene datos binarios (ej. certificados o claves privadas DER), Gossip lo detecta y muestra un visor hexadecimal limpio junto con el número total de bytes.

### Tarjeta de Historial de Versiones
* **Cronología Completa**: Lista todas las versiones ordenadas cronológicamente (las más recientes arriba).
* **Badges de Estado**:
  * `ENABLED` (Activa): Versión consultable y disponible.
  * `DISABLED` (Deshabilitada): Versión suspendida; su valor no puede consultarse hasta reactivarla.
  * `DESTROYED` (Destruida): El contenido fue destruido de forma irreversible.
* **Gestión de Versiones**:
  * **Interruptor Habilitar / Deshabilitar**: Permite activar o suspender versiones específicas (GCP y Azure).
  * **Destruir Versión (Icono de Papelera)**: Destruye el payload de la versión permanentemente tras confirmación de seguridad.
* **Botón Añadir Versión (`+ Nueva Versión`)**:
  Permite rotar o actualizar el valor del secreto añadiendo una nueva versión sin alterar el identificador ni sus etiquetas.

---

## 4. Eliminación de Secretos

Para eliminar un secreto completo:

1. Haz clic en el botón destructivo **Eliminar Secreto** en el panel de detalle.
2. Se mostrará un diálogo de confirmación `Adw.MessageDialog`.
3. Al confirmar, el secreto y todas sus versiones asociadas se eliminarán permanentemente del proveedor en la nube o del archivo Ansible Vault.
