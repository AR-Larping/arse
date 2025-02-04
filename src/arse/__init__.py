import os
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict

app = FastAPI()

# Mount static files from the nix store path
static_path = os.environ.get("STATIC_FILES_PATH")
if static_path:  # In production (nix)
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates_dir = os.environ.get("TEMPLATES_DIR", "templates")
templates = Jinja2Templates(directory=templates_dir)

# Game state
players: Dict[int, int] = {}  # player_id -> steps
winner: int | None = None
WINNING_STEPS = 3

# Reset function for testing
def reset_game():
    global players, winner
    players = {}
    winner = None

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/admin")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"players": players}
    )

@app.post("/create-player", response_class=HTMLResponse)
async def create_player(request: Request):
    player_id = len(players) + 1
    if player_id > 2:
        raise HTTPException(status_code=400, detail="Maximum 2 players allowed")
    players[player_id] = 0
    return templates.TemplateResponse(
        request=request,
        name="player_link.html",
        context={"player_id": player_id}
    )

@app.get("/player/{player_id}", response_class=HTMLResponse)
async def player_page(request: Request, player_id: int):
    if player_id not in players:
        raise HTTPException(status_code=404, detail="Player not found")
    return templates.TemplateResponse(
        request=request,
        name="player.html",
        context={
            "player_id": player_id,
            "steps": players[player_id],
            "winner": winner
        }
    )

@app.post("/player/{player_id}/run", response_class=HTMLResponse)
async def run_step(request: Request, player_id: int):
    if player_id not in players:
        raise HTTPException(status_code=404, detail="Player not found")
    
    global winner
    if winner is not None:
        return templates.TemplateResponse(
            request=request,
            name="game_over.html",
            context={"winner": winner}
        )

    players[player_id] += 1
    if players[player_id] >= WINNING_STEPS:
        winner = player_id

    return templates.TemplateResponse(
        request=request,
        name="player_status.html",
        context={
            "player_id": player_id,
            "steps": players[player_id],
            "winner": winner
        }
    )
