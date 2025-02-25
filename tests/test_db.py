from arse.api import app
from arse.db import reset_game
from fastapi.testclient import TestClient
import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy import text

from arse.db import get_db, create_db_and_tables, reset_game
from arse.models import Player, Base

def setup_function():
    """Reset game state before each test"""
    # Use asyncio to run the async reset_game function
    asyncio.run(reset_game())

def test_admin_page(client):
    response = client.get("/admin")
    assert response.status_code == 200
    # Check for elements that should be in the admin page
    assert "<h1>Game Admin</h1>" in response.text
    assert "player-links" in response.text

@pytest.mark.asyncio
async def test_create_players(client, async_session):
    # Create first player
    response = client.post("/create-player")
    assert response.status_code == 200
    assert "Player 1" in response.text
    
    # Create second player
    response = client.post("/create-player")
    assert response.status_code == 200
    assert "Player 2" in response.text

def test_player_page(client):
    # Create a player first
    client.post("/create-player")
    
    # Check player page
    response = client.get("/player/1")
    assert response.status_code == 200
    # Check for elements that should be in the player page
    assert "<h1>Player" in response.text
    assert "Steps:" in response.text

def test_running_and_winning(client):
    # Create two players
    client.post("/create-player")
    client.post("/create-player")

    # Player 1 takes two steps
    client.post("/player/1/run")
    response = client.post("/player/1/run")
    assert "Steps: 2" in response.text
    assert "won" not in response.text.lower()

    # Player 2 takes one step
    response = client.post("/player/2/run")
    assert "Steps: 1" in response.text
    assert "won" not in response.text.lower()

    # Player 1 wins
    response = client.post("/player/1/run")
    assert "You won!" in response.text

    # Player 2 tries to run after game is over
    response = client.post("/player/2/run")
    assert "Game Over - Player 1 won!" in response.text

# Use in-memory SQLite for testing
@pytest.fixture(name="async_engine")
def async_engine_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    yield engine

@pytest.fixture(name="create_tables")
async def create_tables_fixture(async_engine):
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(name="async_session")
async def async_session_fixture(async_engine, create_tables):
    async with AsyncSession(async_engine) as session:
        yield session

@pytest.mark.asyncio
async def test_create_db_and_tables(async_engine, monkeypatch):
    # Mock the async_engine in the db module
    import arse.db
    monkeypatch.setattr(arse.db, "async_engine", async_engine)
    
    # Call the function to create tables
    await create_db_and_tables()
    
    # Check that tables were created
    async with async_engine.begin() as conn:
        result = await conn.run_sync(lambda sync_conn: sync_conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='player'")
        ))
        tables = result.fetchall()
        assert len(tables) == 1
        assert tables[0][0] == "player"

@pytest.mark.asyncio
async def test_reset_game(async_engine, async_session, monkeypatch):
    # Mock the async_engine in the db module
    import arse.db
    monkeypatch.setattr(arse.db, "async_engine", async_engine)
    
    # Add a player
    player = Player(name="Test Player")
    async_session.add(player)
    await async_session.commit()
    
    # Reset the game
    await reset_game()
    
    # Check that the player table is empty
    result = await async_session.execute(text("SELECT COUNT(*) FROM player"))
    count = result.scalar()
    assert count == 0
