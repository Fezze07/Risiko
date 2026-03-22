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
from web.session import game_session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

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

# ---------------- CARDS API ----------------

class CardSelection(BaseModel):
    indices: List[int]
    player_id: int

@app.get("/player/cards")
async def get_player_cards(player_id: int):
    if not game_session.env or not game_session.env.card_manager:
        return {"cards": []}
    
    hand = game_session.env.card_manager.player_hands.get(player_id, [])
    board = game_session.env.board
    
    serialized_cards = []
    for card in hand:
        # Check if player owns territory for the +2 bonus
        owned = False
        if card.territory_id is not None:
            t = board.territories.get(card.territory_id)
            if t and t.owner_id == player_id:
                owned = True
        
        serialized_cards.append({
            "symbol": card.card_type.name,
            "territory_id": card.territory_id,
            "territory_name": card.territory_name,
            "is_jolly": card.card_type.name == "JOLLY",
            "owns_territory": owned
        })
    
    return {"cards": serialized_cards}

@app.post("/cards/validate")
async def validate_cards(entry: CardSelection):
    if not game_session.env or not game_session.env.card_manager:
        return {"valid": False, "error": "No active game"}
        
    player_id = entry.player_id
    hand = game_session.env.card_manager.player_hands.get(player_id, [])
    
    try:
        selected_cards = [hand[i] for i in entry.indices]
    except (IndexError, TypeError):
        return {"valid": False, "error": "Invalid indices"}

    is_valid = game_session.env.card_manager.validate_combination(selected_cards)
    if not is_valid:
        return {"valid": False}
        
    bonus, t_bonuses = game_session.env.card_manager.calculate_bonus(
        selected_cards, game_session.env.board, player_id
    )
    
    return {
        "valid": True,
        "bonus_armies": bonus,
        "territory_bonuses": t_bonuses
    }

@app.post("/cards/trade")
async def trade_cards(entry: CardSelection):
    if not game_session.env:
        return {"success": False, "error": "No active game"}
    
    if game_session.env.current_phase != "PLAY_CARDS":
        return {"success": False, "error": "Not in PLAY_CARDS phase"}
        
    player_id = entry.player_id
    if player_id != game_session.env.player_turn:
        return {"success": False, "error": "Not your turn"}
    
    # We use step to handle the action properly for rewards/logs
    action = {
        "type": "PLAY_CARDS",
        "cards": entry.indices
    }
    
    # We need to run this in the same way as WebSocket handler would
    # Note: reward/done/info are usually broadcasted. We can trigger state update here
    reward, done, info = game_session.env.step(action, player_id)
    
    if "error" in info:
        return {"success": False, "error": info["error"]}
        
    # Trigger state update via callback to sync all clients (if any)
    if game_session.send_state_update_cb:
        await game_session.state_update()
        
    return {
        "success": True, 
        "armies_to_place": game_session.env.armies_to_place,
        "bonus_armies": info.get("bonus_armies", 0)
    }

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
