# Guía de Instalación

**Gossip** se distribuye tanto en binarios portables independientes precompilados (sin necesidad de instalar librerías adicionales en tu sistema) como en código fuente Python para desarrollo.

---

## 1. Binarios Portables Precompilados (Recomendado)

Cada versión oficial se compila y publica automáticamente a través de GitHub Actions. Estos paquetes integran el intérprete de Python, las librerías nativas GTK4 y Libadwaita, los temas de iconos y los catálogos de internacionalización gettext.

Descarga la última versión desde la [página de Releases en GitHub](https://github.com/sincorchetes/gossip/releases). Verifícala con `sha256sum -c SHA256SUMS.txt` y `gh attestation verify <archivo> -R sincorchetes/gossip` (ver [Seguridad y Privacidad](../security.md)).

=== "Debian / Ubuntu (.deb)"
 
     1. Descarga el paquete para la arquitectura de tu procesador:
        * **Intel / AMD (64-bit)**: `gossip_*_amd64.deb`
        * **ARM 64-bit (Raspberry Pi / ARM)**: `gossip_*_arm64.deb`
     2. Instala el paquete con `apt`:
        ```bash
        sudo apt install ./gossip_*_*.deb
        ```
     3. Abre **Gossip** directamente desde el menú de aplicaciones de tu escritorio o ejecuta `gossip` en la terminal.
 
     > [!TIP]
     > **Integración completa de escritorio:** El paquete `.deb` registra automáticamente el icono en alta resolución, el lanzador `.desktop` en el menú del sistema y permite desinstalar limpiamente con `sudo apt remove gossip`.
 
=== "Fedora / openSUSE (.rpm)"
 
     1. Descarga el archivo para la arquitectura de tu procesador:
        * **Intel / AMD (64-bit)**: `gossip-*-1.x86_64.rpm`
        * **ARM 64-bit (aarch64)**: `gossip-*-1.aarch64.rpm`
     2. Instala el paquete con el gestor de software de tu distribución:
        * **Fedora / RHEL**:
          ```bash
          sudo dnf install ./gossip-*-1.*.rpm
          ```
        * **openSUSE (Tumbleweed / Leap)**:
          ```bash
          sudo zypper install ./gossip-*-1.*.rpm
          ```
     3. Abre **Gossip** desde el menú de aplicaciones o escribe `gossip` en tu terminal.
 
=== "Linux Portable (.tar.gz)"
 
     1. Descarga el paquete `gossip-linux-x86_64-v*.tar.gz` (o `gossip-linux-aarch64-v*.tar.gz` para ARM64) de la última publicación.
     2. Descomprime el tarball en tu terminal:
        ```bash
        tar -xvf gossip-linux-*-v*.tar.gz
        cd gossip/
        ```
     3. Ejecuta el binario:
        ```bash
        ./gossip
        ```
 
     > [!NOTE]
     > Compatible con distribuciones modernas de Linux con glibc 2.35+ y servidor gráfico Wayland o X11.
 
=== "Windows (64-bit)"
 
     **Instalador (recomendado)**
 
     1. Descarga `gossip-windows-x64-v*.msi` de la última publicación.
     2. Haz doble clic en el `.msi`, acepta la licencia y pulsa **Install**. El asistente termina con una pantalla *Completed*; Gossip se instala en `C:\Program Files\Gossip` y se añade un acceso directo **Gossip** al menú Inicio.
     3. Para actualizar, ejecuta el `.msi` más reciente: sustituye la versión anterior. Se desinstala desde *Configuración → Aplicaciones*.
 
     **Portable (.zip)**
 
     1. Descarga `gossip-windows-x64-v*.zip` de la última publicación.
     2. Descomprime el archivo ZIP en cualquier ubicación (ej. tu carpeta de usuario).
     3. Haz doble clic en `gossip.exe` para iniciar la aplicación.
 
     > [!TIP]
     > **Autocontenido:** Ambos paquetes incluyen todo lo necesario. No necesitas tener instalado Python, MSYS2 ni GTK en tu sistema.
 
     > [!NOTE]
     > Solo se publican compilaciones x64. Windows on ARM puede ejecutarlas mediante la emulación x64 incluida en Windows. El instalador no está firmado, por lo que SmartScreen puede mostrar una advertencia: elige **Más información → Ejecutar de todas formas**.

=== "macOS"

     1. Descarga la imagen de disco que corresponda a tu Mac de la última publicación:
        * **Apple Silicon (M1 y posteriores)**: `gossip-macos-arm64-v*.dmg`
        * **Intel**: `gossip-macos-x86_64-v*.dmg`
 
        ¿No sabes cuál tienes? Abre **menú Apple → Acerca de este Mac**: *Chip: Apple M…* indica Apple Silicon; *Procesador: Intel…* indica Intel. Con la compilación equivocada macOS indica que la app no es compatible.
     2. Abre el `.dmg` y arrastra `gossip.app` a **Aplicaciones**.
     3. La app no está firmada ni notarizada, así que macOS bloquea el primer arranque (*"No se puede abrir gossip porque es de un desarrollador no identificado"*). Permítela una vez con una de estas opciones:
        * **Clic derecho → Abrir** sobre `gossip.app` y confirma **Abrir**; o
        * Terminal:
          ```bash
          xattr -dr com.apple.quarantine /Applications/gossip.app
          ```
     4. Si la app no arranca, ejecútala desde la terminal para ver el error:
        ```bash
        /Applications/gossip.app/Contents/MacOS/gossip
        ```
        Añade `--debug` (o define `GOSSIP_DEBUG=1`) para ver diagnósticos detallados en stderr, y `--self-test` para comprobar que todas las librerías incluidas cargan sin abrir ventana.
 
     > [!NOTE]
     > También se publica un `gossip-macos-<arq>-v*.tar.gz` portable con el mismo `gossip.app`.

---

## Flatpak (Linux)

Cada versión adjunta también un paquete `gossip-<arq>-v*.flatpak` para `x86_64` y `aarch64`. Se ejecuta en un sandbox sobre el runtime GNOME 51 de Flathub:

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Platform//51
flatpak install --user --bundle gossip-x86_64-v*.flatpak
flatpak run com.github.sincorchetes.gossip_gcp
```

Un paquete no contiene el runtime, así que debe venir de Flathub. Fedora trae su propio remoto de Flatpak y no Flathub; sin las dos primeras líneas la instalación falla con *«requiere el tiempo de ejecución org.gnome.Platform/x86_64/51 que no se encontró»*. Los paquetes llevan además la dirección de Flathub, de modo que la herramienta puede ofrecerse a añadirlo sola.

El sandbox da a Gossip acceso a la red y acceso de solo lectura a las carpetas de credenciales que usan los proveedores (`~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.kube`, `~/.vault-token`). Las variables de entorno de tu shell no llegan hasta él: consulta [Variables de Entorno](../environment.md#flatpak) para `--env` y `flatpak override`. Cómo compilarlo tú mismo se explica en [CI/CD y Publicaciones](../cicd.md).

---

## 2. Nix Flake y Devenv

Si utilizas Nix o [devenv.sh](https://devenv.sh), Gossip incluye un entorno declarativo y reproducible con todas las dependencias de GTK4, Libadwaita y Python preconfiguradas:

```bash
# Clonar el repositorio
git clone https://github.com/sincorchetes/gossip.git
cd gossip/

# Entrar al shell aislado con todas las herramientas
devenv shell

# Iniciar la aplicación
gossip
```

O ejecutar la suite de pruebas completa:
```bash
devenv test
```

---

## 3. Ejecución desde Código Fuente (Poetry)

Si deseas colaborar en el desarrollo de Gossip o ejecutarlo directamente desde código fuente en Linux o macOS:

### Requisitos del Sistema

Se requiere **Python 3.14+**, **GTK4 (>= 4.12)**, **Libadwaita (>= 1.4)** y **PyGObject**:

=== "Debian / Ubuntu 24.04+"

    ```bash
    sudo apt update
    sudo apt install -y python3-dev python3-pip \
      libgtk-4-dev libadwaita-1-dev \
      python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 \
      adwaita-icon-theme
    ```

=== "Fedora 39+"

    ```bash
    sudo dnf install -y python3-devel gtk4-devel libadwaita-devel \
      python3-gobject adwaita-icon-theme
    ```

=== "Arch Linux"

    ```bash
    sudo pacman -S --needed python gtk4 libadwaita python-gobject \
      adwaita-icon-theme
    ```

=== "macOS (Homebrew)"

    ```bash
    brew install python gtk4 libadwaita gobject-introspection adwaita-icon-theme
    ```

### Instalación de Dependencias Python

Utilizando [Poetry](https://python-poetry.org/):

```bash
# Instalar dependencias del proyecto
poetry install

# Ejecutar la aplicación Gossip
poetry run gossip
```

Para ejecutar con parámetros específicos:
```bash
poetry run python src/main.py --provider gcp --lang es
```
