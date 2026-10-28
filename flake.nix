{
  description = "Gossip: graphical secret manager for GCP, AWS, Azure, Ansible Vault, Vault/OpenBao and Kubernetes";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      version = "0.0.1";
    in
    {
      packages = forAllSystems (pkgs: rec {
        gossip = pkgs.callPackage (
          {
            lib,
            stdenv,
            python3,
            wrapGAppsHook4,
            gobject-introspection,
            gtk4,
            libadwaita,
            adwaita-icon-theme,
            glib-networking,
          }:
          let
            # Not in nixpkgs yet; a pure-Python wrapper over ansible-core.
            ansible-vault = python3.pkgs.buildPythonPackage rec {
              pname = "ansible-vault";
              version = "4.1.0";
              pyproject = true;

              src = pkgs.fetchPypi {
                pname = "ansible_vault";
                inherit version;
                hash = "sha256-fphakynkcolh16APYkEvqOwkak2DKtbm0VgWXgAmUps=";
              };

              build-system = [ python3.pkgs.setuptools ];
              dependencies = with python3.pkgs; [
                ansible-core
                pyyaml
              ];

              doCheck = false;
              pythonImportsCheck = [ "ansible_vault" ];
            };

            pythonEnv = python3.withPackages (
              ps: with ps; [
                pygobject3
                google-cloud-secret-manager
                google-auth
                boto3
                botocore
                awscrt
                azure-keyvault-secrets
                azure-identity
                pyyaml
                cryptography
                ansible-vault
              ]
            );
          in
          stdenv.mkDerivation {
            pname = "gossip";
            inherit version;

            src = lib.fileset.toSource {
              root = ./.;
              fileset = lib.fileset.unions [
                ./src
                ./locales
                ./data
              ];
            };

            nativeBuildInputs = [
              wrapGAppsHook4
              gobject-introspection
            ];

            buildInputs = [
              gtk4
              libadwaita
              adwaita-icon-theme
              glib-networking
            ];

            dontBuild = true;
            dontWrapGApps = true;

            # The app resolves `locales/` next to the `src` package, so both are
            # installed side by side instead of as a wheel.
            installPhase = ''
              runHook preInstall

              mkdir -p $out/lib/gossip $out/share/applications $out/share/metainfo
              cp -r src locales $out/lib/gossip/
              find $out/lib/gossip -name __pycache__ -type d -prune -exec rm -rf {} +

              cp -r data/icons $out/share/icons
              cp data/*.desktop $out/share/applications/
              cp data/*.metainfo.xml $out/share/metainfo/

              runHook postInstall
            '';

            preFixup = ''
              makeWrapper ${pythonEnv.interpreter} $out/bin/gossip \
                --add-flags $out/lib/gossip/src/main.py \
                "''${gappsWrapperArgs[@]}"
            '';

            meta = {
              description = "Graphical secret manager for GCP, AWS, Azure, Ansible Vault, Vault/OpenBao and Kubernetes";
              homepage = "https://sincorchetes.github.io/gossip/";
              license = lib.licenses.gpl3Plus;
              mainProgram = "gossip";
              platforms = lib.platforms.linux;
            };
          }
        ) { };

        default = gossip;
      });

      apps = forAllSystems (pkgs: rec {
        gossip = {
          type = "app";
          program = "${self.packages.${pkgs.system}.gossip}/bin/gossip";
        };
        default = gossip;
      });

      formatter = forAllSystems (pkgs: pkgs.nixfmt-rfc-style);
    };
}
