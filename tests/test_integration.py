import pytest
import asyncio
from httpx import AsyncClient
from fastapi.testclient import TestClient
from arse.models import Base, Player
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from arse.api import app
from arse.db import get_db, create_db_and_tables

# We'll use the fixtures from conftest.py

@pytest.mark.asyncio
async def test_create_and_get_player():
    # Create a test client
    client = TestClient(app, base_url="http://test")
    
    # Create a player through the API
    response = client.post("/create-player")
    assert response.status_code == 200
    assert "Player 1" in response.text
    
    # Get the player through the API
    response = client.get("/players/")
    assert response.status_code == 200
    players = response.json()
    assert len(players) == 1
    assert players[0]["name"] == "Player 1" 