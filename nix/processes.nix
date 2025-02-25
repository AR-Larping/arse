{
  inputs,
  lib,
  config,
  ...
}: {
  perSystem = { config, self', inputs', pkgs, system, ... }: {
    # Create a wrapper script for process-compose
    apps.proc-wrapper = {
      type = "app";
      program = toString (pkgs.writeShellScript "proc-wrapper" ''
        # Run process-compose with the --keep-project flag
        exec ${pkgs.process-compose}/bin/process-compose --keep-project up "$@"
      '');
    };
    
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
                restart = "no";
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
            };

            "2_webserver" = {
              command = toString (pkgs.writeShellScript "start-webserver" ''
                export PATH="${config.postgresql.package}/bin:$PATH"
                
                # Read the PostgreSQL port
                if [ -f "$PWD/run/postgres_port" ]; then
                  PORT=$(cat "$PWD/run/postgres_port")
                else
                  echo "PostgreSQL port file not found. Exiting."
                  exit 1
                fi
                
                export STATIC_FILES_PATH="${config.static-files}/static"
                export DB_HOST="localhost"
                export DB_PORT="$PORT"
                export DB_NAME="arse"
                export DB_USER="postgres"
                export DATABASE_URL="postgresql+asyncpg://postgres@localhost:$PORT/arse"
                export TEMPLATES_DIR="${config.templates}"
                
                # Wait for PostgreSQL to be ready with a more robust check
                echo "Waiting for PostgreSQL to be ready on port $PORT..."
                for i in {1..60}; do
                  if pg_isready -h localhost -p $PORT -q; then
                    echo "PostgreSQL is accepting connections!"
                    
                    # Try to connect to the actual database
                    if psql -h localhost -p $PORT -d arse -c "SELECT 1" >/dev/null 2>&1; then
                      echo "Successfully connected to the arse database!"
                      break
                    else
                      echo "PostgreSQL is running but arse database is not ready yet..."
                    fi
                  fi
                  
                  echo "Waiting for PostgreSQL... ($i/60)"
                  sleep 1
                  
                  if [ $i -eq 60 ]; then
                    echo "PostgreSQL did not start in time. Exiting."
                    exit 1
                  fi
                done
                
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