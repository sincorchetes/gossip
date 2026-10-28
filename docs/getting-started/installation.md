# Installation Guide

**Gossip** is distributed both as standalone pre-compiled portable binaries (with zero system dependencies) and as an open-source Python package.

---

## 1. Pre-built Standalone Binaries (Recommended)

Official binary bundles are automatically built and published for each release via GitHub Actions. These packages bundle the complete Python runtime, GTK4, Libadwaita, icon themes, and gettext translation catalogs.

Download the latest version from the [GitHub Releases page](https://github.com/sincorchetes/gossip/releases). Verify it with `sha256sum -c SHA256SUMS.txt` and `gh attestation verify <file> -R sincorchetes/gossip` (see [Security & Privacy](../security.md)).

=== "Debian / Ubuntu (.deb)"

    1. Download the package for your CPU architecture from the latest release:
       * **Intel / AMD (64-bit)**: `gossip_*_amd64.deb`
       * **ARM 64-bit (Raspberry Pi / ARM)**: `gossip_*_arm64.deb`
    2. Install the package using `apt`:
       ```bash
       sudo apt install ./gossip_*_*.deb
       ```
    3. Launch **Gossip** from your application menu or run `gossip` in your terminal.

    > [!TIP]
    > **Desktop Integration:** The `.deb` package automatically registers the application icon, desktop launcher (`.desktop`), and provides seamless uninstallation via `sudo apt remove gossip`.

=== "Fedora / openSUSE (.rpm)"

    1. Download the package for your CPU architecture from the latest release:
       * **Intel / AMD (64-bit)**: `gossip-*-1.x86_64.rpm`
       * **ARM 64-bit (aarch64)**: `gossip-*-1.aarch64.rpm`
    2. Install the package using your system package manager:
       * **Fedora / RHEL**:
         ```bash
         sudo dnf install ./gossip-*-1.*.rpm
         ```
       * **openSUSE (Tumbleweed / Leap)**:
         ```bash
         sudo zypper install ./gossip-*-1.*.rpm
         ```
    3. Launch **Gossip** from your application menu or run `gossip` in your terminal.

=== "Linux Portable (.tar.gz)"

    1. Download `gossip-linux-x86_64-v*.tar.gz` (or `gossip-linux-aarch64-v*.tar.gz` for ARM64) from the latest release.
    2. Extract the tarball:
       ```bash
       tar -xvf gossip-linux-*-v*.tar.gz
       cd gossip/
       ```
    3. Run the executable:
       ```bash
       ./gossip
       ```

    > [!NOTE]
    > Compatible with all modern Linux distributions running glibc 2.35+ and an active Wayland or X11 compositor.

=== "Windows (64-bit)"

    **Installer (recommended)**

    1. Download `gossip-windows-x64-v*.msi` from the latest release.
    2. Double-click the `.msi`, accept the license and click **Install**. The wizard ends with a *Completed* page; Gossip is installed in `C:\Program Files\Gossip` and a **Gossip** shortcut is added to the Start menu.
    3. Updating is done by running the newer `.msi`; it replaces the previous version. Uninstall from *Settings → Apps*.

    **Portable (.zip)**

    1. Download `gossip-windows-x64-v*.zip` from the latest release.
    2. Extract the ZIP archive to any folder (e.g., your user directory).
    3. Double-click `gossip.exe` to launch the application.

    > [!TIP]
    > **Self-contained:** Both packages bundle everything needed. You do not need to install Python, MSYS2, or GTK separately.

    > [!NOTE]
    > Only x64 builds are published. Windows on ARM can run them through Windows' built-in x64 emulation. The installer is not code-signed, so SmartScreen may show a warning: choose **More info → Run anyway**.

=== "macOS"

    1. Download the disk image that matches your Mac from the latest release:
       * **Apple Silicon (M1 and later)**: `gossip-macos-arm64-v*.dmg`
       * **Intel**: `gossip-macos-x86_64-v*.dmg`

       Not sure which one you have? Open **Apple menu → About This Mac**: *Chip: Apple M…* means Apple Silicon; *Processor: Intel…* means Intel. Using the wrong build shows the app as unsupported.
    2. Open the `.dmg` and drag `gossip.app` to **Applications**.
    3. The app is not signed or notarized, so macOS blocks the first launch (*"gossip cannot be opened because it is from an unidentified developer"*). Allow it once with either:
       * **Right-click → Open** on `gossip.app`, then confirm **Open**; or
       * Terminal:
         ```bash
         xattr -dr com.apple.quarantine /Applications/gossip.app
         ```
    4. If the app does not start, run it from the terminal to see the error:
       ```bash
       /Applications/gossip.app/Contents/MacOS/gossip
       ```
       Add `--debug` (or set `GOSSIP_DEBUG=1`) for detailed diagnostics on stderr, and `--self-test` to check that all bundled libraries load without opening a window.

    > [!NOTE]
    > A portable `gossip-macos-<arch>-v*.tar.gz` with the same `gossip.app` is also published.

---

## Flatpak (Linux)

Each release also attaches a `gossip-<arch>-v*.flatpak` bundle for `x86_64` and `aarch64`. It runs against the GNOME 51 runtime from Flathub, in a sandbox:

```bash
flatpak remote-add --if-not-exists --user flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.gnome.Platform//51
flatpak install --user --bundle gossip-x86_64-v*.flatpak
flatpak run com.github.sincorchetes.gossip_gcp
```

A bundle does not contain the runtime, so it has to come from Flathub. Fedora ships with its own Flatpak remote and not Flathub; without the first two lines the installation fails with *"requires the runtime org.gnome.Platform/x86_64/51 which was not found"*. The bundles also carry the Flathub address, so the tool can offer to add it by itself.

The sandbox gives Gossip network access and read-only access to the credential folders the providers use (`~/.aws`, `~/.azure`, `~/.config/gcloud`, `~/.kube`, `~/.vault-token`). Your shell's environment variables do not reach it: see [Environment Variables](../environment.md#flatpak) for `--env` and `flatpak override`. Building it yourself is described in [CI/CD & Releases](../cicd.md).

---

## 2. Nix, NixOS & Devenv

The repository ships a `flake.nix` that builds Gossip with GTK4, Libadwaita and every Python dependency, so it works on NixOS and on any Linux with Nix and flakes enabled (`x86_64-linux` and `aarch64-linux`). Gossip is not in nixpkgs yet.

### Try it without installing

```bash
# Run it once
nix run github:sincorchetes/gossip

# Or open a shell with `gossip` in the PATH (gone when you exit)
nix shell github:sincorchetes/gossip
gossip
```

Pass options after `--`: `nix run github:sincorchetes/gossip -- --provider aws --lang en`. Add `--refresh` to pick up a newer commit, or pin a tag or commit: `github:sincorchetes/gossip/v0.0.1`.

### Install it for your user

```bash
nix profile install github:sincorchetes/gossip
nix profile remove gossip      # to uninstall
```

The desktop launcher and icon are installed too, so Gossip shows up in your application menu.

### NixOS or Home Manager configuration

Add the flake as an input and install the package:

```nix
# flake.nix
{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    gossip.url = "github:sincorchetes/gossip";
    # Optional: reuse your nixpkgs instead of fetching another one.
    # It must provide Python 3.14.
    # gossip.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { nixpkgs, gossip, ... }: {
    nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
      modules = [
        ({ pkgs, ... }: {
          environment.systemPackages = [
            gossip.packages.${pkgs.stdenv.hostPlatform.system}.default
          ];
          # Home Manager: home.packages = [ ...same package... ];
        })
      ];
    };
  };
}
```

Then `sudo nixos-rebuild switch --flake .#myhost`.

> [!NOTE]
> The wrapper clears `PYTHONPATH`, so a Python environment inherited from your shell (for example a devenv shell) cannot shadow Gossip's own dependencies.

### Development environment (devenv)

If you want to work on Gossip, [devenv.sh](https://devenv.sh) gives you a reproducible environment with all GTK4, Libadwaita and Python dependencies pre-configured:

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

You can also build the flake from a checkout with `nix build .#gossip` and run `./result/bin/gossip`.

---

## 3. Running from Source (Poetry)

If you wish to develop Gossip or run it directly from source on Linux or macOS:

### Prerequisites

You need **Python 3.14+**, **GTK4 (>= 4.12)**, **Libadwaita (>= 1.4)**, and **PyGObject**:

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
