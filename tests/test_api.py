import pytest
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from httpx import AsyncClient
from fastapi.testclient import TestClient

from arse.api import app
from arse.models import Player, Base

# We'll use the client fixture from conftest.py instead

# Test routes
@pytest.mark.asyncio
async def test_root():
    # Create a test client that follows redirects
    client = TestClient(app, base_url="http://test")
    
    # Use the client directly for this test
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}

@pytest.mark.asyncio
async def test_get_players():
    # Create a test client
    client = TestClient(app, base_url="http://test")
    
    # Create a player through the API
    response = client.post("/create-player")
    # We don't need to check the response, just that the player was created
    
    # Get the player through the API
    response = client.get("/players/")
    assert response.status_code == 200
    players = response.json()
    assert len(players) == 1
    assert players[0]["name"] == "Player 1"

# Add synchronous tests that use the TestClient
def test_admin_page(client):
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Create Player" in response.text

def test_create_player(client):
    response = client.post("/create-player")
    assert response.status_code == 200
    assert "/player/1" in response.text 