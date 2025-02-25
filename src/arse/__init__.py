import os
import asyncio
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, Optional
import psycopg
from contextlib import asynccontextmanager

app = FastAPI()

# Mount static files from the nix store path
static_path = os.environ.get("STATIC_FILES_PATH")
if static_path:  # In production (nix)
    app.mount("/static", StaticFiles(directory=static_path), name="static")

templates_dir = os.environ.get("TEMPLATES_DIR", "templates")
templates = Jinja2Templates(directory=templates_dir)

# Game constants
WINNING_STEPS = 3

# Database connection with better error handling and retry logic
async def get_db():
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "arse")
    db_user = os.environ.get("DB_USER", os.environ.get("USER", "postgres"))
    db_password = os.environ.get("DB_PASSWORD", "")
    
    conn_string = f"host={db_host} port={db_port} dbname={db_name} user={db_user}"
    if db_password:
        conn_string += f" password={db_password}"
    
    max_retries = 5
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            conn = await psycopg.AsyncConnection.connect(conn_string, autocommit=True)
            cur = conn.cursor()
            
            # Test the connection with a simple query
            await cur.execute("SELECT 1")
            await cur.fetchone()
            
            try:
                yield cur
            finally:
                await cur.close()
                await conn.close()
            return
        except Exception as e:
            print(f"Database connection error (attempt {attempt+1}/{max_retries}): {e}")
            
            # If the database doesn't exist, try to create it
            if "database \"arse\" does not exist" in str(e) and attempt == 0:
                try:
                    # Connect to the default database (usually named after the user)
                    default_db = os.environ.get("USER", "postgres")
                    default_conn_string = f"host={db_host} port={db_port} dbname={default_db} user={db_user}"
                    if db_password:
                        default_conn_string += f" password={db_password}"
                    
                    default_conn = await psycopg.AsyncConnection.connect(default_conn_string, autocommit=True)
                    default_cur = default_conn.cursor()
                    
                    # Create the arse database
                    await default_cur.execute("CREATE DATABASE arse")
                    
                    await default_cur.close()
                    await default_conn.close()
                    
                    print("Created arse database")
                    # Don't increment attempt counter to retry with the new database
                    continue
                except Exception as inner_e:
                    print(f"Failed to create database: {inner_e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                # Last attempt failed, raise the exception
                raise

# Setup database tables with better error handling
async def init_db():
    try:
        async for db in get_db():
            try:
                await db.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    steps INTEGER NOT NULL DEFAULT 0
                )
                """)
                
                await db.execute("""
                CREATE TABLE IF NOT EXISTS game_state (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    winner INTEGER NULL REFERENCES players(id)
                )
                """)
                
                # Ensure we have a game state row
                await db.execute("SELECT id FROM game_state WHERE id = 1")
                if await db.fetchone() is None:
                    await db.execute("INSERT INTO game_state (id, winner) VALUES (1, NULL)")
                
                print("Database tables initialized successfully")
                return
            except Exception as e:
                print(f"Error initializing database tables: {e}")
                raise
    except Exception as e:
        print(f"Failed to connect to database for initialization: {e}")
        raise

# Reset function for testing
async def reset_game():
    db = await anext(get_db().__aiter__())
    
    # Drop and recreate tables
    await db.execute("DROP TABLE IF EXISTS players CASCADE")
    await db.execute("DROP TABLE IF EXISTS game_state CASCADE")
    
    # Recreate tables
    await init_db()

# Lifespan event to initialize database on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database on startup
    await init_db()
    yield

# Add lifespan event to FastAPI app
app.router.lifespan_context = lifespan

@app.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/admin")

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, db = Depends(get_db)):
    await db.execute("SELECT id, steps FROM players ORDER BY id")
    players = {row[0]: row[1] for row in await db.fetchall()}
    
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"players": players}
    )

@app.post("/create-player", response_class=HTMLResponse)
async def create_player(request: Request, db = Depends(get_db)):
    await db.execute("SELECT COUNT(*) FROM players")
    count = await db.fetchone()
    
    if count[0] >= 2:
        raise HTTPException(status_code=400, detail="Maximum 2 players allowed")
    
    await db.execute("INSERT INTO players (steps) VALUES (0) RETURNING id")
    player_id = (await db.fetchone())[0]
    
    return templates.TemplateResponse(
        request=request,
        name="player_link.html",
        context={"player_id": player_id}
    )

@app.get("/player/{player_id}", response_class=HTMLResponse)
async def player_page(request: Request, player_id: int, db = Depends(get_db)):
    await db.execute("SELECT id FROM players WHERE id = %s", (player_id,))
    if await db.fetchone() is None:
        raise HTTPException(status_code=404, detail="Player not found")
    
    await db.execute("SELECT steps FROM players WHERE id = %s", (player_id,))
    steps = (await db.fetchone())[0]
    
    await db.execute("SELECT winner FROM game_state WHERE id = 1")
    winner = (await db.fetchone())[0]
    
    return templates.TemplateResponse(
        request=request,
        name="player.html",
        context={
            "player_id": player_id,
            "steps": steps,
            "winner": winner
        }
    )

@app.post("/player/{player_id}/run", response_class=HTMLResponse)
async def run_step(request: Request, player_id: int, db = Depends(get_db)):
    await db.execute("SELECT id FROM players WHERE id = %s", (player_id,))
    if await db.fetchone() is None:
        raise HTTPException(status_code=404, detail="Player not found")
    
    await db.execute("SELECT winner FROM game_state WHERE id = 1")
    winner = (await db.fetchone())[0]
    
    if winner is not None:
        return templates.TemplateResponse(
            request=request,
            name="game_over.html",
            context={"winner": winner}
        )

    # Increment steps
    await db.execute("UPDATE players SET steps = steps + 1 WHERE id = %s RETURNING steps", (player_id,))
    steps = (await db.fetchone())[0]
    
    # Check for winner
    if steps >= WINNING_STEPS:
        await db.execute("UPDATE game_state SET winner = %s WHERE id = 1", (player_id,))
        winner = player_id

    return templates.TemplateResponse(
        request=request,
        name="player_status.html",
        context={
            "player_id": player_id,
            "steps": steps,
            "winner": winner
        }
    )
