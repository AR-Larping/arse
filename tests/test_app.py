import pytest
import asyncio
from arse.api import app
from fastapi.testclient import TestClient
from arse.db import reset_game

# This is a synchronous wrapper around the async reset_game function
def sync_reset_game():
    asyncio.run(reset_game())

def setup_function():
    """Reset game state before each test"""
    sync_reset_game()


def test_admin_page(client):
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Create Player" in response.text

def test_create_players(client):
    # Create first player
    response = client.post("/create-player")
    assert response.status_code == 200
    assert "Player 1" in response.text

    # Create second player
    response = client.post("/create-player")
    assert response.status_code == 200
    assert "Player 2" in response.text

    # Try to create third player (should fail)
    response = client.post("/create-player")
    assert response.status_code == 400

def test_player_page(client):
    # Create a player first
    client.post("/create-player")
    
    # Check player page
    response = client.get("/player/1")
    assert response.status_code == 200
    assert "Run!" in response.text
    assert "Steps: 0" in response.text

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
