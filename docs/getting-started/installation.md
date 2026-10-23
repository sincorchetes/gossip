# Installation Guide

**Gossip** is distributed both as standalone pre-compiled portable binaries (with zero system dependencies) and as an open-source Python package.

---

## 1. Pre-built Standalone Binaries (Recommended)

Official binary bundles are automatically built and published for each release via GitHub Actions. These packages bundle the complete Python runtime, GTK4, Libadwaita, icon themes, and gettext translation catalogs.

Download the latest version from the [GitHub Releases page](https://github.com/sincorchetes/gossip/releases).

=== "Debian / Ubuntu (.deb)"

    1. Download `gossip_*_amd64.deb` from the latest release.
    2. Install the package using `apt`:
       ```bash
       sudo apt install ./gossip_*_amd64.deb
       ```
    3. Launch **Gossip** from your application menu or run `gossip` in your terminal.

    > [!TIP]
    > **Desktop Integration:** The `.deb` package automatically registers the application icon, desktop launcher (`.desktop`), and provides seamless uninstallation via `sudo apt remove gossip`.

=== "Fedora / openSUSE (.rpm)"

    1. Download `gossip-*-1.x86_64.rpm` from the latest release.
    2. Install the package using your system package manager:
       * **Fedora / RHEL**:
         ```bash
         sudo dnf install ./gossip-*-1.x86_64.rpm
         ```
       * **openSUSE (Tumbleweed / Leap)**:
         ```bash
         sudo zypper install ./gossip-*-1.x86_64.rpm
         ```
    3. Launch **Gossip** from your application menu or run `gossip` in your terminal.

=== "Linux Portable (.tar.gz)"

    1. Download `gossip-linux-x86_64-v*.tar.gz` from the latest release.
    2. Extract the tarball:
       ```bash
       tar -xvf gossip-linux-x86_64-v*.tar.gz
       cd gossip/
       ```
    3. Run the executable:
       ```bash
       ./gossip
       ```

    > [!NOTE]
    > Compatible with all modern Linux distributions running glibc 2.35+ and an active Wayland or X11 compositor.

=== "Windows (64-bit)"

    1. Download `gossip-windows-x64-v*.zip` from the latest release.
    2. Extract the ZIP archive to any folder (e.g., `C:\Program Files\Gossip` or your user directory).
    3. Double-click `gossip.exe` to launch the application.

    > [!TIP]
    > **Zero installation required:** The Windows package is fully self-contained. You do not need to install Python, MSYS2, or GTK separately.

---

## 2. Nix Flake & Devenv

If you use Nix or [devenv.sh](https://devenv.sh), Gossip includes a reproducible developer environment with all GTK4, Libadwaita, and Python dependencies pre-configured:

```bash
# Clone the repository
git clone https://github.com/sincorchetes/gossip.git
cd gossip/

# Enter the isolated environment with all tools
devenv shell

# Launch the application
gossip
```

Or run tests directly:
```bash
devenv test
```

---

## 3. Running from Source (Poetry)

If you wish to develop Gossip or run it directly from source on Linux or macOS:

### Prerequisites

You need **Python 3.10+**, **GTK4 (>= 4.12)**, **Libadwaita (>= 1.4)**, and **PyGObject**:

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

### Install Python Dependencies

Using [Poetry](https://python-poetry.org/):

```bash
# Install package dependencies
poetry install

# Run the Gossip application
poetry run gossip
```

To run with specific flags:
```bash
poetry run python src/main.py --provider gcp --lang en
```
