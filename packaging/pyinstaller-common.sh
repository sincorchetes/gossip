# Options shared by every platform build (Linux, Windows, macOS).
# Source this file from the workflow, then run:
#   pyinstaller "${PYI_COMMON_ARGS[@]}" <platform-specific options> src/main.py
PYI_COMMON_ARGS=(
  --noconfirm --onedir --windowed --name "gossip"
  --collect-all "gi"
  --collect-data "ansible.config"
  --hidden-import "gi"
  --hidden-import "gi.repository.Gtk"
  --hidden-import "gi.repository.Adw"
  --hidden-import "gi.repository.Gio"
  --hidden-import "gi.repository.GLib"
  --hidden-import "gi.repository.GObject"
  --exclude-module "ansible.cli"
  --exclude-module "ansible.plugins"
  --exclude-module "ansible.executor"
  --exclude-module "ansible.playbook"
)
