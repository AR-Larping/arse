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
            "0_init_db" = {
              command = toString self'.apps.init-db.program;
              depends_on = {};
              log_location = "./run/init-db.log";
              availability = {
                exit_on_end = true;
              };
            };
            
            "1_database" = {
              command = toString self'.apps.start-db.program;
              depends_on = {
                "0_init_db" = {
                  condition = "process_completed_successfully";
                };
              };
              log_location = "./run/database.log";
              readiness_probe = {
                exec = {
                  command = "${config.postgresql.package}/bin/pg_isready -h localhost -p 5432";
                };
                initial_delay_seconds = 2;
                period_seconds = 5;
              };
            };

            "2_webserver" = {
              command = toString (pkgs.writeShellScript "start-webserver" ''
                export STATIC_FILES_PATH="${config.static-files}/static"
                export DB_HOST="localhost"
                export DB_PORT="5432"
                export DB_NAME="arse"
                export DB_USER="$(whoami)"
                export TEMPLATES_DIR="${config.templates}"
                
                exec ${toString self'.apps.serve.program}
              '');
              depends_on = {
                "1_database" = {
                  condition = "process_started";
                };
              };
              log_location = "./run/webserver.log";
              readiness_probe = {
                http_get = {
                  host = "127.0.0.1";
                  port = 8000;
                  path = "/admin";
                };
                initial_delay_seconds = 5;
                period_seconds = 10;
              };
            };

            "3_process_compose" = {
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