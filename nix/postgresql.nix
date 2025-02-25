{ lib, ... }:

{
  perSystem = { config, self', inputs', pkgs, system, ... }: {
    # Define options for the perSystem scope
    options.postgresql = lib.mkOption {
      type = lib.types.attrsOf lib.types.anything;
      default = {};
      description = "PostgreSQL configuration";
    };
    
    # Define the configuration for the perSystem scope
    config = {
      # Set default values for options
      postgresql.package = pkgs.postgresql_15;
      
      # Create apps for PostgreSQL management
      apps = {
        # Initialize the database
        init-db = {
          type = "app";
          program = toString (pkgs.writeShellScript "init-postgres" ''
            export PATH="${config.postgresql.package}/bin:$PATH"
            
            # Initialize PostgreSQL database
            PGDATA="$PWD/run/postgres"
            
            # Find an available port
            PORT=$(${pkgs.python3}/bin/python -c '
import socket
s = socket.socket()
s.bind(("", 0))
print(s.getsockname()[1])
s.close()
')
            echo "Using port $PORT for PostgreSQL"
            
            # Store the port for later use
            mkdir -p "$PWD/run"
            echo "$PORT" > "$PWD/run/postgres_port"
            
            # Force clean start by removing the data directory
            if [ -d "$PGDATA" ]; then
              echo "Removing existing PostgreSQL data directory for clean start..."
              rm -rf "$PGDATA"
            fi
            
            echo "Initializing PostgreSQL database in $PGDATA"
            initdb -D "$PGDATA"
            
            # Configure PostgreSQL to listen on localhost with the dynamic port
            echo "Configuring PostgreSQL..."
            cat > "$PGDATA/postgresql.conf" <<'PGCONF'
# -----------------------------
# PostgreSQL configuration file
# -----------------------------

listen_addresses = 'localhost'
port = $PORT
PGCONF

            # Replace $PORT with the actual port number
            sed -i.bak "s/\$PORT/$PORT/" "$PGDATA/postgresql.conf"
            
            # Start PostgreSQL
            echo "Starting PostgreSQL to create/update database..."
            pg_ctl -D "$PGDATA" -l "$PGDATA/logfile" start
            
            # Wait for PostgreSQL to start
            echo -n "waiting for server to start..."
            until pg_isready -h localhost -p $PORT -q; do
              echo -n "."
              sleep 0.1
            done
            echo " done"
            echo "server started"
            
            # Create postgres role
            echo "Creating postgres role..."
            psql -h localhost -p $PORT -d postgres -c "CREATE ROLE postgres WITH LOGIN SUPERUSER;" || echo "Role postgres may already exist"
            
            # Create application database directly (not in a function)
            echo "Creating application database 'arse'..."
            psql -h localhost -p $PORT -d postgres -c "CREATE DATABASE arse;" || echo "Database may already exist"
            
            # Grant permissions
            echo "Granting permissions..."
            psql -h localhost -p $PORT -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE arse TO postgres;" || true
            
            # Stop PostgreSQL
            echo -n "waiting for server to shut down..."
            pg_ctl -D "$PGDATA" stop -m fast
            echo " done"
            echo "server stopped"
            
            echo "Database initialization complete."
          '');
        };
        
        # Start the database
        start-db = {
          type = "app";
          program = toString (pkgs.writeShellScript "start-database" ''
            export PATH="${config.postgresql.package}/bin:$PATH"
            
            PGDATA="$PWD/run/postgres"
            
            # Read the port from the file
            if [ -f "$PWD/run/postgres_port" ]; then
              PORT=$(cat "$PWD/run/postgres_port")
            else
              # Find an available port if the file doesn't exist
              PORT=$(${pkgs.python3}/bin/python -c '
import socket
s = socket.socket()
s.bind(("", 0))
print(s.getsockname()[1])
s.close()
')
              echo "$PORT" > "$PWD/run/postgres_port"
            fi
            echo "Using port $PORT for PostgreSQL"
            
            # Check if PostgreSQL is already running
            if pg_isready -h localhost -p $PORT -q; then
              echo "PostgreSQL is already running. Stopping it first..."
              pg_ctl -D "$PGDATA" stop -m fast || true
              sleep 2
            fi
            
            # Clean up any stale lock files
            if [ -f "$PGDATA/postmaster.pid" ]; then
              echo "Removing stale lock file..."
              rm -f "$PGDATA/postmaster.pid"
            fi
            
            # Make sure pg_hba.conf is properly configured
            cat > "$PGDATA/pg_hba.conf" <<'PGHBA'
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             all                                     trust
host    all             all             127.0.0.1/32            trust
host    all             all             ::1/128                 trust
PGHBA
            
            # Update the port in postgresql.conf
            cat > "$PGDATA/postgresql.conf" <<'PGCONF'
# -----------------------------
# PostgreSQL configuration file
# -----------------------------

listen_addresses = 'localhost'
port = $PORT
PGCONF

            # Replace $PORT with the actual port number
            sed -i.bak "s/\$PORT/$PORT/" "$PGDATA/postgresql.conf"
            
            # Start PostgreSQL
            echo "Starting PostgreSQL database from $PGDATA on port $PORT"
            pg_ctl -D "$PGDATA" -l "$PGDATA/logfile" start
            
            # Verify the arse database exists and is accessible
            echo "Verifying arse database..."
            if ! psql -h localhost -p $PORT -d arse -c "SELECT 1" >/dev/null 2>&1; then
              echo "Creating arse database..."
              createdb -h localhost -p $PORT arse
              echo "Creating postgres role..."
              psql -h localhost -p $PORT -d postgres -c "CREATE ROLE postgres WITH LOGIN SUPERUSER;" || echo "Role may already exist"
              echo "Granting permissions..."
              psql -h localhost -p $PORT -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE arse TO postgres;" || true
            fi
            
            # Debug: List all databases
            echo "Available databases:"
            psql -h localhost -p $PORT -l
            
            # Keep the script running
            echo "PostgreSQL is running on port $PORT. Press Ctrl+C to stop."
            tail -f "$PGDATA/logfile"
          '');
        };
        
        # Create a test script to verify the database connection
        test-db = {
          type = "app";
          program = toString (pkgs.writeShellScript "test-postgres" ''
            export PATH="${config.postgresql.package}/bin:$PATH"
            
            if [ -f "$PWD/run/postgres_port" ]; then
              PORT=$(cat "$PWD/run/postgres_port")
              echo "Testing PostgreSQL connection on port $PORT..."
              
              # Test basic connection
              if pg_isready -h localhost -p $PORT; then
                echo "✅ Basic connection successful"
              else
                echo "❌ Basic connection failed"
                exit 1
              fi
              
              # Test database connection
              if psql -h localhost -p $PORT -d postgres -c "SELECT 1" >/dev/null 2>&1; then
                echo "✅ Database connection successful"
              else
                echo "❌ Database connection failed"
                exit 1
              fi
              
              # List databases
              echo "Available databases:"
              psql -h localhost -p $PORT -l
            else
              echo "PostgreSQL port file not found"
              exit 1
            fi
          '');
        };
      };
    };
  };
} 