{
  pkgs,
  lib,
  config,
  ...
}:
{
  # Native packages for GTK4, Libadwaita and uv
  packages = with pkgs; [
    gtk4
    libadwaita
    gobject-introspection
    graphene
    pango.out
    gdk-pixbuf
    harfbuzz
    adwaita-icon-theme
    uv
    gettext
    xvfb-run
  ];

  env = {
    GI_TYPELIB_PATH = "${lib.makeSearchPath "lib/girepository-1.0" (
      with pkgs;
      [
        gtk4
        libadwaita
        gobject-introspection
        graphene
        pango.out
        gdk-pixbuf
        harfbuzz
      ]
    )}";
  };

  # devenv.sh/languages/
  languages.python = {
    enable = true;
    package = pkgs.python313;
    uv.enable = true;
    poetry.enable = true;
    venv.enable = true;
    venv.requirements = ./requirements.txt;
  };

  enterShell = ''
    export PYTHONPATH="${pkgs.python313Packages.pygobject3}/${pkgs.python313Packages.pygobject3.pythonModule.sitePackages}:$PYTHONPATH"
    export NO_MKDOCS_2_WARNING=1
  '';

  # Scripts / shortcuts
  scripts.gossip.exec = ''
    python src/main.py "$@"
  '';

  scripts.test.exec = ''
    pytest "$@"
  '';

  scripts.coverage.exec = ''
    pytest --cov=src --cov-report=term-missing "$@"
  '';

  scripts.docs.exec = ''
    NO_MKDOCS_2_WARNING=1 python -m mkdocs serve "$@"
  '';

  scripts.docs-build.exec = ''
    NO_MKDOCS_2_WARNING=1 python -m mkdocs build "$@"
  '';

  enterTest = ''
    if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
      if command -v xvfb-run >/dev/null 2>&1; then
        exec xvfb-run -a pytest "$@"
      fi
    fi
    if [ -w /dev/tty ]; then
      set -o pipefail
      pytest 2>&1 | tee /dev/tty
    else
      pytest
    fi
  '';


  # See full reference at https://devenv.sh/reference/options/
}
