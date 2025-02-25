from fastapi.templating import Jinja2Templates
import tempfile
import os
import pathlib

# Create a temporary directory for templates
temp_dir = tempfile.mkdtemp(prefix="arse_test_templates_")
templates_dir = temp_dir
static_dir = os.path.join(templates_dir, "static")
pathlib.Path(static_dir).mkdir(parents=True, exist_ok=True)

# Create mock template files
with open(os.path.join(templates_dir, "admin.html"), "w") as f:
    f.write("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Game Admin</title>
    </head>
    <body>
        <h1>Game Admin</h1>
        
        {% if game_over %}
            <p>Game is over! Player {{ winner }} won.</p>
            <form action="/reset-game" method="post">
                <button type="submit">Reset Game</button>
            </form>
        {% else %}
            <h2>Create Player</h2>
            <form action="/create-player" method="post">
                <button type="submit">Create Player</button>
            </form>
        {% endif %}
        
        <div id="player-links">
            <!-- Player links will be added here -->
        </div>
    </body>
    </html>
    """)

with open(os.path.join(templates_dir, "player.html"), "w") as f:
    f.write("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Player {{ player.id }}</title>
    </head>
    <body>
        <h1>Player {{ player.id }}</h1>
        
        <p>Steps: {{ player.steps }}</p>
        
        {% if message %}
            <p>{{ message }}</p>
        {% endif %}
        
        {% if not game_over %}
            <form action="/player/{{ player.id }}/run" method="post">
                <button type="submit">Run!</button>
            </form>
        {% endif %}
        
        <p><a href="/admin">Back to Admin</a></p>
    </body>
    </html>
    """)

# Create static files
with open(os.path.join(static_dir, "htmx.min.js"), "w") as f:
    f.write("// Mock HTMX for testing")

with open(os.path.join(static_dir, "simple.min.css"), "w") as f:
    f.write("/* Mock CSS for testing */")

# Create templates object
templates = Jinja2Templates(directory=templates_dir) 