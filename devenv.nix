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
    ruff
    sonar-scanner-cli
    openjdk
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
    package = pkgs.python314;
    uv.enable = true;
    poetry.enable = true;
    venv.enable = true;
    venv.requirements = ./requirements.txt;
  };

  enterShell = ''
    export PYTHONPATH="${pkgs.python314Packages.pygobject3}/${pkgs.python314Packages.pygobject3.pythonModule.sitePackages}:$PYTHONPATH"
    export PATH="${pkgs.ruff}/bin:$PATH"
    if [ -d .devenv/state/venv/bin ]; then
      ln -sf "${pkgs.ruff}/bin/ruff" .devenv/state/venv/bin/ruff
    fi
    export NO_MKDOCS_2_WARNING=1
    # Configure SonarQube scanner to use NixOS JDK (avoids dynamically linked executable error)
    export SONAR_SCANNER_JAVA_EXE_PATH="${pkgs.openjdk}/bin/java"
    export JAVA_HOME="${pkgs.openjdk}"
  '';

  # Scripts / shortcuts
  scripts.gossip.exec = ''
    python src/main.py "$@"
  '';

  scripts.fmt.exec = ''
    ruff format src tests "$@"
    ruff check --fix src tests "$@"
  '';

  scripts.lint.exec = ''
    ruff check src tests "$@"
    ruff format --check src tests "$@"
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

  # Graphify knowledge graph (output in graphify-out/, ignored by git).
  # The semantic pass (docs/images) uses a local OpenAI-compatible server (llama.cpp);
  # override GRAPHIFY_BASE_URL / GRAPHIFY_MODEL to point elsewhere. Code is indexed with AST only.
  scripts.graph.exec = ''
    export OPENAI_BASE_URL="''${GRAPHIFY_BASE_URL:-http://127.0.0.1:9090/v1}"
    export OPENAI_API_KEY="''${OPENAI_API_KEY:-local}"
    graphify . --backend openai --model "''${GRAPHIFY_MODEL:-ornith-ai/Ornith-1.5-9B-GGUF}" "$@"
  '';

  scripts.graph-code.exec = ''
    graphify . --code-only "$@"
  '';

  scripts.graph-update.exec = ''
    graphify update . "$@"
  '';

  scripts.graph-watch.exec = ''
    graphify watch . "$@"
  '';

  git-hooks.hooks = {
    ruff.enable = true;
    ruff-format.enable = true;
  };

  scripts.typecheck.exec = ''
    mypy "$@"
  '';

  enterTest = ''
    mypy || exit 1
    if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
      if command -v xvfb-run >/dev/null 2>&1; then
        exec xvfb-run -a pytest "$@"
      fi
    fi
    pytest "$@"
  '';


  # See full reference at https://devenv.sh/reference/options/
}
