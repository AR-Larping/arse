{ lib, ... }:

{
  perSystem = { config, self', inputs', pkgs, system, ... }: {
    # Define options for the perSystem scope
    options.postgresql = {
      package = lib.mkOption {
        type = lib.types.package;
        description = "The PostgreSQL package to use";
      };
      
      configFile = lib.mkOption {
        type = lib.types.package;
        description = "The PostgreSQL configuration file";
      };
      
      dataDir = lib.mkOption {
        type = lib.types.str;
        default = "./run/postgres";
        description = "Directory for PostgreSQL data";
      };
    };
    
    # Define the configuration for the perSystem scope
    config = {
      # Set default values for options
      postgresql = {
        # Use PostgreSQL without additional extensions
        package = pkgs.postgresql_15;
        
        configFile = pkgs.writeTextFile {
          name = "postgresql.conf";
          text = ''
            # Basic PostgreSQL configuration
            listen_addresses = 'localhost'
            port = 5432
            
            # Memory settings
            shared_buffers = '128MB'
            
            # Logging
            log_destination = 'stderr'
            
            # Autovacuum settings
            autovacuum = on
          '';
        };
      };
      
      # Define the apps
      apps = {
        init-db = {
          type = "app";
          program = toString (pkgs.writeShellScript "init-db" ''
            set -e
            
            # Create the run directory if it doesn't exist
            mkdir -p "$(dirname "${config.postgresql.dataDir}")"
            
            DB_DIR="$(cd "$(dirname "${config.postgresql.dataDir}")" && pwd)/$(basename "${config.postgresql.dataDir}")"
            POSTGRES="${config.postgresql.package}/bin"
            
            # Set environment variables for easier access
            export PGDATA="$DB_DIR"
            export PGHOST="$DB_DIR"
            export PGPORT="5432"
            
            # Check if the database is already initialized
            if [ -f "$DB_DIR/PG_VERSION" ]; then
              echo "PostgreSQL database already initialized in $DB_DIR"
            else
              echo "Initializing PostgreSQL database in $DB_DIR"
              # Remove the directory if it exists but is not a valid database
              if [ -d "$DB_DIR" ]; then
                rm -rf "$DB_DIR"
              fi
              mkdir -p "$DB_DIR"
              $POSTGRES/initdb -D "$DB_DIR" --auth=trust --no-locale --encoding=UTF8
              
              # Directly append to the configuration file
              cat >> "$DB_DIR/postgresql.conf" <<-EOF
listen_addresses = 'localhost'
port = 5432
EOF
              
              # Simple pg_hba.conf
              cat > "$DB_DIR/pg_hba.conf" << 'EOT'
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
EOT
            fi
            
            # Start PostgreSQL temporarily
            echo "Starting PostgreSQL to create/update database..."
            $POSTGRES/pg_ctl -D "$DB_DIR" start -w
            
            # Create application database if needed
            if ! $POSTGRES/psql -h localhost -p 5432 -lqt | cut -d \| -f 1 | grep -qw arse; then
              echo "Creating application database 'arse'..."
              $POSTGRES/createdb -h localhost arse
            fi
            
            # Stop PostgreSQL
            $POSTGRES/pg_ctl -D "$DB_DIR" stop
            
            echo "Database initialization complete."
          '');
        };

        start-db = {
          type = "app";
          program = toString (pkgs.writeShellScript "start-db" ''
            set -e
            
            # Create the run directory if it doesn't exist
            mkdir -p "$(dirname "${config.postgresql.dataDir}")"
            
            DB_DIR="$(cd "$(dirname "${config.postgresql.dataDir}")" && pwd)/$(basename "${config.postgresql.dataDir}")"
            POSTGRES="${config.postgresql.package}/bin"
            
            # Check if the database is initialized
            if [ ! -f "$DB_DIR/PG_VERSION" ]; then
              echo "Database not initialized. Run 'nix run .#init-db' first."
              exit 1
            fi
            
            # Ensure proper permissions
            chmod 700 "$DB_DIR"
            
            # Handle signals properly
            cleanup() {
              echo "Shutting down PostgreSQL..."
              $POSTGRES/pg_ctl -D "$DB_DIR" stop -m fast
              exit 0
            }
            
            trap cleanup SIGINT SIGTERM
            
            echo "Starting PostgreSQL database from $DB_DIR"
            $POSTGRES/postgres -D "$DB_DIR" &
            PG_PID=$!
            
            # Wait for PostgreSQL to exit
            wait $PG_PID
          '');
        };
      };
    };
  };
} 