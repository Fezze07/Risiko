import sys
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from web.sockets import ws_game_handler

app = FastAPI(title="Risiko Web")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/web/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def get_player_colors(n: int) -> Dict[int, str]:
    total = max(2, int(n))
    return {
        player_id: f"hsl({int((player_id * (360 / total)) % 360)}, 70%, 50%)"
        for player_id in range(1, total + 1)
    }


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.get("/app")
async def app_page():
    return FileResponse(str(STATIC_DIR / "app.html"))

@app.websocket("/ws/game")
async def ws_game(ws: WebSocket):
    raw_players = ws.query_params.get("num_players", "2")
    try:
        initial_num_players = int(raw_players)
    except (TypeError, ValueError):
        initial_num_players = 2
    initial_num_players = max(2, min(8, initial_num_players))
    await ws_game_handler(
        ws,
        initial_num_players=initial_num_players,
        color_provider=get_player_colors,
    )
