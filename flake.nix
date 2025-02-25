{
  description = "Hello world flake using uv2nix";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Add static dependencies
    htmx = {
      url = "https://unpkg.com/htmx.org@2.0.0/dist/htmx.min.js";
      flake = false;
    };

    simple-css = {
      url = "https://cdn.simplecss.org/simple.min.css";
      flake = false;
    };

    process-compose-flake = {
      url = "github:Platonic-Systems/process-compose-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = ["x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin"];
      imports = [ 
        ./nix/webserver.nix
        ./nix/postgresql.nix
        ./nix/processes.nix
        inputs.process-compose-flake.flakeModule
      ];

      perSystem = { config, self', inputs', pkgs, system, ... }: let
        python = pkgs.python312;
        workspace = inputs.uv2nix.lib.workspace.loadWorkspace { 
          workspaceRoot = ./.;
        };

        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        # Add test overrides
        pyprojectOverrides = final: prev: {
          arse = prev.arse.overrideAttrs (old: {
            passthru = old.passthru // {
              tests = let
                virtualenv = final.mkVirtualEnv "arse-test-env" {
                  arse = [ "test" ];
                };
              in (old.tests or { }) // {
                pytest = pkgs.stdenv.mkDerivation {
                  name = "${final.arse.name}-pytest";
                  inherit (final.arse) src;
                  nativeBuildInputs = [ virtualenv ];
                  dontConfigure = true;

                  buildPhase = ''
                    runHook preBuild
                    cp -r ${final.arse.src}/tests .
                    cp -r ${final.arse.src}/src .
                    PYTHONPATH=$PWD/src pytest -v tests/
                    runHook postBuild
                  '';

                  PYTEST_ADDOPTS="--import-mode=importlib";

                  installPhase = ''
                    runHook preInstall
                    touch $out
                    runHook postInstall
                  '';
                };
              };
            };
          });
        };

        pythonSet = (pkgs.callPackage inputs.pyproject-nix.build.packages {
          inherit python;
        }).overrideScope (
          pkgs.lib.composeManyExtensions [
            inputs.pyproject-build-systems.overlays.default
            overlay
            pyprojectOverrides
          ]
        );

        pythonEnv = pythonSet.mkVirtualEnv "arse-env" workspace.deps.default;
      in {
        # Configure the pythonEnv for the webserver module
        pythonEnv = pythonEnv;

        packages = {
          default = pythonEnv;
        };

        apps = {
          default = {
            type = "app";
            program = "${pythonEnv}/bin/hello";
          };
        };

        checks = {
          inherit (pythonSet.arse.passthru.tests) pytest;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python312
            uv
            ruff
            python312Packages.python-lsp-ruff
            pyright
            nixpkgs-fmt
            python312Packages.psycopg
          ];
          shellHook = ''
            export PYTHONPATH=${toString ./.}/src:$PYTHONPATH
            export TEMPLATES_DIR=${toString ./.}/templates
          '';
        };
      };
    };
} 