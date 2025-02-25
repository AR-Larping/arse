from fastapi import FastAPI, Depends, HTTPException, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path
from contextlib import asynccontextmanager

from .db import get_db, create_db_and_tables, reset_game, DATABASE_URL
from .models import Player, PlayerRead

import os
import logging
import pathlib
import tempfile
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for the FastAPI app."""
    logger.info("Starting up application")
    
    try:
        # Wait for database to be available
        for i in range(5):
            try:
                await create_db_and_tables()
                logger.info("Database tables created")
                break
            except Exception as e:
                if i < 4:  # Try 5 times
                    logger.warning(f"Database connection attempt {i+1} failed: {e}")
                    await asyncio.sleep(2)  # Wait before retrying
                else:
                    raise
        
        await create_db_and_tables()
        logger.info("Database tables created")
        yield
    except Exception as e:
        logger.error(f"Database error: {e}")
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        logger.info("Shutting down application")

# Create FastAPI app
app = FastAPI(lifespan=lifespan)

# Setup templates
templates_dir = Path(os.getenv("TEMPLATES_DIR", "templates"))
if not templates_dir.exists():
    logger.warning(f"Templates directory not found: {templates_dir}")
    templates_dir = Path(tempfile.mkdtemp(prefix="arse_templates_"))
    logger.info(f"Created temporary templates directory: {templates_dir}")

logger.info(f"Using templates directory: {templates_dir}")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files
static_dir = templates_dir / "static"
try:
    if not static_dir.exists():
        static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
except (PermissionError, OSError) as e:
    logger.warning(f"Could not create static directory: {e}")
    # Create a temporary directory for static files
    temp_static = Path(tempfile.mkdtemp(prefix="arse_static_"))
    logger.info(f"Using temporary static directory: {temp_static}")
    static_dir = temp_static
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(temp_static)), name="static")

# Game state
game_state = {
    "players": [],
    "winner": None,
    "game_over": False
}

# Example route
@app.get("/")
async def root():
    return {"message": "Hello World"}

# Example route with database access
@app.get("/players/")
async def get_players(db: AsyncSession = Depends(get_db)):
    statement = select(Player)
    result = await db.execute(statement)
    players = result.scalars().all()
    return players

# Admin page
@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(
        request,
        "admin.html", 
        {"game_over": game_state["game_over"], "winner": game_state["winner"]}
    )

# Create player
@app.post("/create-player")
async def create_player(request: Request, db: AsyncSession = Depends(get_db)):
    # Check if game is over
    if game_state["game_over"]:
        return HTMLResponse("Game is over. Cannot create new players.", status_code=400)
    
    # Check if we already have 2 players
    if len(game_state["players"]) >= 2:
        return HTMLResponse("Maximum number of players reached.", status_code=400)
    
    # Create a new player
    player = Player(name=f"Player {len(game_state['players']) + 1}")
    db.add(player)
    await db.commit()
    await db.refresh(player)
    
    # Add player to game state
    game_state["players"].append({"id": len(game_state["players"]) + 1, "steps": 0})
    
    # Redirect to player page
    return RedirectResponse(url=f"/player/{len(game_state['players'])}", status_code=303)

# Player page
@app.get("/player/{player_id}", response_class=HTMLResponse)
async def player_page(request: Request, player_id: int):
    if player_id < 1 or player_id > len(game_state["players"]):
        return HTMLResponse("Player not found", status_code=404)
    
    player = game_state["players"][player_id - 1]
    
    return templates.TemplateResponse(
        request,
        "player.html", 
        {
            "player": player,
            "game_over": game_state["game_over"],
            "winner": game_state["winner"]
        }
    )

# Run action
@app.post("/player/{player_id}/run", response_class=HTMLResponse)
async def run_action(request: Request, player_id: int):
    if player_id < 1 or player_id > len(game_state["players"]):
        return HTMLResponse("Player not found", status_code=404)
    
    if game_state["game_over"]:
        winner_id = game_state["winner"]
        return templates.TemplateResponse(
            request,
            "player.html", 
            {
                "player": game_state["players"][player_id - 1],
                "game_over": True,
                "winner": winner_id,
                "message": f"Game Over - Player {winner_id} won!"
            }
        )
    
    player = game_state["players"][player_id - 1]
    player["steps"] += 1
    
    # Check for winner
    if player["steps"] >= 3:
        game_state["game_over"] = True
        game_state["winner"] = player_id
        return templates.TemplateResponse(
            request,
            "player.html", 
            {
                "player": player,
                "game_over": True,
                "winner": player_id,
                "message": "You won!"
            }
        )
    
    return templates.TemplateResponse(
        request,
        "player.html", 
        {
            "player": player,
            "game_over": False,
            "winner": None
        }
    )

# Reset game
@app.post("/reset-game")
async def reset_game_route():
    await reset_game()
    game_state["players"] = []
    game_state["winner"] = None
    game_state["game_over"] = False
    return RedirectResponse(url="/admin", status_code=303)

# Add more routes as needed 