import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from arse.models import Player, Base

# Use in-memory SQLite for testing
@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)

def test_player_model():
    # Create an in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create a player
    player = Player(name="Test Player", email="test@example.com")
    
    # Save to database
    with Session(engine) as session:
        session.add(player)
        session.commit()
        session.refresh(player)
        
        # Query the player
        db_player = session.execute(select(Player).where(Player.name == "Test Player")).scalar_one()
        
        # Check that the player was saved correctly
        assert db_player.id is not None
        assert db_player.name == "Test Player"
        assert db_player.email == "test@example.com"

def test_create_player(session):
    # Create a player
    player = Player(name="Test Player", email="test@example.com")
    session.add(player)
    session.commit()
    
    # Refresh to get the ID
    session.refresh(player)
    
    # Check that the player was created with an ID
    assert player.id is not None
    assert player.name == "Test Player"
    assert player.email == "test@example.com"

def test_create_player_without_email(session):
    # Create a player without an email
    player = Player(name="No Email")
    session.add(player)
    session.commit()
    
    # Refresh to get the ID
    session.refresh(player)
    
    # Check that the player was created with an ID
    assert player.id is not None
    assert player.name == "No Email"
    assert player.email is None 