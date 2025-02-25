from typing import AsyncGenerator, Optional
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import logging
import asyncio
import asyncpg

from .models import Base

# Setup logging
logger = logging.getLogger(__name__)

# Get database URL from environment or use default
# Try to read port from file if not in environment
db_port = os.getenv('DB_PORT')
if not db_port and os.path.exists("run/postgres_port"):
    try:
        with open("run/postgres_port", "r") as f:
            db_port = f.read().strip()
    except Exception as e:
        logger.warning(f"Could not read port from file: {e}")
        db_port = "5432"  # Default fallback
else:
    db_port = db_port or "5432"  # Default fallback

# Default to PostgreSQL with environment-specific settings
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"postgresql+asyncpg://{os.getenv('DB_USER', 'postgres')}@{os.getenv('DB_HOST', 'localhost')}:{db_port}/{os.getenv('DB_NAME', 'arse')}"
)

# Use SQLite for testing
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
if TEST_MODE:
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Log the database URL (without sensitive info)
db_url_for_log = DATABASE_URL.split("@")[0].split(":")
if len(db_url_for_log) > 2:
    # Hide password in logs
    db_url_for_log[2] = "****"
db_url_for_log = ":".join(db_url_for_log)
if "@" in DATABASE_URL:
    db_url_for_log += "@" + DATABASE_URL.split("@")[1]
logger.info(f"Using database: {db_url_for_log}")

# Create async engine
async_engine = create_async_engine(
    DATABASE_URL,
    # These connect_args are needed for SQLite
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

# Create async session factory
async_session = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

# Function to create tables
async def create_db_and_tables():
    try:
        # Debug: Print available roles in PostgreSQL
        try:
            # Connect using the same port as the main connection
            conn_str = f"postgresql://postgres@localhost:{db_port}/postgres"
            conn = await asyncpg.connect(conn_str)
            roles = await conn.fetch("SELECT rolname FROM pg_roles")
            logger.info(f"Available PostgreSQL roles: {[r['rolname'] for r in roles]}")
            await conn.close()
        except Exception as e:
            logger.error(f"Could not connect to PostgreSQL for debugging: {e}")
        
        async with async_engine.begin() as conn:
            # Create tables if they don't exist
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        
        # Provide helpful error messages for common PostgreSQL issues
        if "role" in str(e) and "does not exist" in str(e):
            logger.error("PostgreSQL user does not exist.")
            logger.error("Make sure your postgresql.nix configuration includes this user.")
            logger.error("You can also set DATABASE_URL environment variable to use a different user.")
        elif "database" in str(e) and "does not exist" in str(e):
            logger.error("PostgreSQL database does not exist.")
            logger.error("You need to create the database first:")
            logger.error("  sudo -u postgres createdb arse")
        elif "password authentication failed" in str(e):
            logger.error("PostgreSQL password authentication failed.")
            logger.error("Check your DATABASE_URL or postgresql.nix configuration.")
        elif "Connection refused" in str(e):
            logger.error("PostgreSQL connection refused.")
            logger.error("Make sure PostgreSQL service is running:")
            logger.error("  sudo systemctl start postgresql")
        raise

# Dependency to get a database session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

# Reset function for testing
async def reset_game():
    async with async_engine.begin() as conn:
        # Drop and recreate tables
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all) 