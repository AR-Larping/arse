{
  inputs,
  lib,
  config,
  ...
}: {
  perSystem = { config, self', inputs', pkgs, system, ... }: {
    # Define the options we want to use
    options = {
      pythonEnv = lib.mkOption {
        type = lib.types.package;
        description = "Python environment containing the application";
      };

      static-files = lib.mkOption {
        type = lib.types.package;
        description = "Directory containing static files";
      };

      templates = lib.mkOption {
        type = lib.types.package;
        description = "Directory containing templates";
      };
    };

    # Define the configuration
    config = {
      # Create static files directory
      static-files = pkgs.runCommand "static-files" {} ''
        mkdir -p $out/static
        cp ${inputs.htmx} $out/static/htmx.min.js
        cp ${inputs.simple-css} $out/static/simple.min.css
      '';

      # Create templates directory
      templates = pkgs.runCommand "templates" {} ''
        mkdir -p $out
        echo "Copying templates from ${toString ./../templates}"
        ls -la ${toString ./../templates}
        cp -v ${toString ./../templates}/* $out/
        echo "Contents of $out:"
        ls -la $out
      '';

      apps.serve = {
        type = "app";
        program = toString (pkgs.writeShellScript "serve" ''
          export STATIC_FILES_PATH=${config.static-files}/static
          export TEMPLATES_DIR=${config.templates}
          ${config.pythonEnv}/bin/uvicorn src.arse:app --host 127.0.0.1 --port 8000 --reload
        '');
      };
    };
  };
} 