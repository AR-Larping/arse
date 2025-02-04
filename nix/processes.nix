{
  inputs,
  lib,
  config,
  ...
}: {
  perSystem = { config, self', inputs', pkgs, system, ... }: {
    process-compose = {
      proc = {
        settings = {
          processes = {
            "1_webserver" = {
              command = toString self'.apps.serve.program;
              environment = {
                STATIC_FILES_PATH = "${config.static-files}/static";
              };
              log_location = "./run/webserver.log";
              readiness_probe = {
                http_get = {
                  host = "127.0.0.1";
                  port = 8000;
                };
                initial_delay_seconds = 2;
                period_seconds = 10;
              };
            };

            "2_process_compose" = {
              command = "tail -f -n100 process-compose-$USER.log";
              working_dir = "/tmp";
              log_location = "./run/process-compose.log";
            };
          };
        };
      };
    };
  };
} 