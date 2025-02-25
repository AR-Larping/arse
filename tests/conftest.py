import sys
from pathlib import Path
import pytest
import os
import pathlib
import asyncio
import tempfile
from fastapi.testclient import TestClient
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import StaticPool
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker

# Set TEST_MODE environment variable
os.environ["TEST_MODE"] = "true"
# Override DATABASE_URL to use in-memory SQLite
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

# Add the src directory to Python path
src_path = str(Path(__file__).parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Now import from arse after setting up the environment
from arse.models import Base
from arse.db import reset_game

# Fixture for templates
@pytest.fixture(scope="session")
def templates_dir():
    """Create a temporary directory with test templates."""
    # Create a temporary directory for templates
    temp_dir = Path(tempfile.mkdtemp(prefix="arse_test_templates_"))
    os.environ["TEMPLATES_DIR"] = str(temp_dir)
    
    # Ensure the directory exists
    temp_dir.mkdir(exist_ok=True)
    static_dir = temp_dir / "static"
    static_dir.mkdir(exist_ok=True)
    
    # Copy test templates to the temporary directory
    templates_source = Path(__file__).parent / "templates"
    if not templates_source.exists():
        raise RuntimeError(f"Test templates directory not found: {templates_source}")
    
    # Copy template files
    (temp_dir / "admin.html").write_text((templates_source / "admin.html").read_text())
    (temp_dir / "player.html").write_text((templates_source / "player.html").read_text())
    
    # Copy static files
    (static_dir / "htmx.min.js").write_text((templates_source / "static" / "htmx.min.js").read_text())
    (static_dir / "simple.min.css").write_text((templates_source / "static" / "simple.min.css").read_text())
    
    yield temp_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)

# Fixture for app with templates
@pytest.fixture(scope="session")
def app_with_templates(templates_dir):
    """Configure the app with test templates."""
    # Import app
    from arse.api import app
    
    # Create templates object for tests
    templates = Jinja2Templates(directory=str(templates_dir))
    static_dir = templates_dir / "static"
    
    # Override app's templates
    import arse.api
    arse.api.templates = templates
    arse.api.static_dir = str(static_dir)
    
    # Re-mount static files
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # Ensure database is created for tests
    asyncio.run(arse.db.create_db_and_tables())
    
    return app

# Fixture for test client
@pytest.fixture
def client(app_with_templates):
    """Create a test client for the app."""
    return TestClient(app_with_templates)

# Fixture for async engine
@pytest.fixture(name="async_engine")
def async_engine_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    yield engine

# Fixture for async session
@pytest.fixture
async def async_session(async_engine):
    async with AsyncSession(async_engine) as session:
        # Create tables
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        yield session
        
        # Drop tables
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

# Synchronous wrapper for reset_game
@pytest.fixture(autouse=True)
def reset_db_before_test():
    asyncio.run(reset_game())
    
    # Reset game state in the API
    import arse.api
    arse.api.game_state = {
        "players": [],
        "winner": None,
        "game_over": False
    }

# Override the database connection for tests
@pytest.fixture(scope="session", autouse=True)
def override_db_connection():
    """Override the database connection to use the test database."""
    # Import the database module
    import arse.db
    
    # Create a test engine
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    
    # Override the engine and session
    arse.db.async_engine = test_engine
    arse.db.async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create tables
    async def setup():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    asyncio.run(setup())
    
    yield
    
    # Cleanup
    async def cleanup():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    asyncio.run(cleanup()) 