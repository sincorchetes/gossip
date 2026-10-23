# Guía de Instalación

**Gossip** se distribuye tanto en binarios portables independientes precompilados (sin necesidad de instalar librerías adicionales en tu sistema) como en código fuente Python para desarrollo.

---

## 1. Binarios Portables Precompilados (Recomendado)

Cada versión oficial se compila y publica automáticamente a través de GitHub Actions. Estos paquetes integran el intérprete de Python, las librerías nativas GTK4 y Libadwaita, los temas de iconos y los catálogos de internacionalización gettext.

Descarga la última versión desde la [página de Releases en GitHub](https://github.com/sincorchetes/gossip/releases).

=== "Debian / Ubuntu (.deb)"
 
     1. Descarga el paquete `gossip_*_amd64.deb` de la última publicación.
     2. Instala el paquete con `apt`:
        ```bash
        sudo apt install ./gossip_*_amd64.deb
        ```
     3. Abre **Gossip** directamente desde el menú de aplicaciones de tu escritorio o ejecuta `gossip` en la terminal.
 
     > [!TIP]
     > **Integración completa de escritorio:** El paquete `.deb` registra automáticamente el icono en alta resolución, el lanzador `.desktop` en el menú del sistema y permite desinstalar limpiamente con `sudo apt remove gossip`.
 
=== "Fedora / openSUSE (.rpm)"
 
     1. Descarga el archivo `gossip-*-1.x86_64.rpm` de la última publicación.
     2. Instala el paquete con el gestor de software de tu distribución:
        * **Fedora / RHEL**:
          ```bash
          sudo dnf install ./gossip-*-1.x86_64.rpm
          ```
        * **openSUSE (Tumbleweed / Leap)**:
          ```bash
          sudo zypper install ./gossip-*-1.x86_64.rpm
          ```
     3. Abre **Gossip** desde el menú de aplicaciones o escribe `gossip` en tu terminal.
 
=== "Linux Portable (.tar.gz)"
 
     1. Descarga el paquete `gossip-linux-x86_64-v*.tar.gz` de la última publicación.
     2. Descomprime el tarball en tu terminal:
        ```bash
        tar -xvf gossip-linux-x86_64-v*.tar.gz
        cd gossip/
        ```
     3. Ejecuta el binario:
        ```bash
        ./gossip
        ```
 
     > [!NOTE]
     > Compatible con distribuciones modernas de Linux con glibc 2.35+ y servidor gráfico Wayland o X11.
 
=== "Windows (64-bit)"
 
     1. Descarga el archivo `gossip-windows-x64-v*.zip` de la última publicación.
     2. Descomprime el archivo ZIP en cualquier ubicación (ej. `C:\Program Files\Gossip` o en tu carpeta de usuario).
     3. Haz doble clic en `gossip.exe` para iniciar la aplicación.
 
     > [!TIP]
     > **Sin instalación previa:** El paquete de Windows es totalmente autocontenido. No necesitas tener instalado Python, MSYS2 ni GTK en tu sistema.

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

Se requiere **Python 3.10+**, **GTK4 (>= 4.12)**, **Libadwaita (>= 1.4)** y **PyGObject**:

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
