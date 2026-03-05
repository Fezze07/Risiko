import math
import os
from typing import Dict, List, Any

from ai.agent import Agent
from config import Config
from core.environment import RisikoEnvironment
from core.world import TERRITORIES
from utils.trainer_utils import TrainerUtils


# Carica best_agent.pkl per creare un agente AI.
def build_ai_agent(env: RisikoEnvironment, agent_id: int = 2) -> Agent:
    ai_agent = Agent(env.board, id=agent_id)
    # Updated path to dataset folder
    model_path = os.path.join("dataset", "best_agent.pkl")
    saved = TrainerUtils.load_weights(model_path)
    if saved is not None:
        try:
            ai_agent.nn.set_weights(saved)
            ai_agent.epsilon = 0.0
            return ai_agent
        except Exception:
            pass
    ai_agent.epsilon = 1.0
    return ai_agent


# ================================
# 🌎 WORLD MAP LAYOUT (viewBox 0 0 1000 600)
# Coordinate posizionate geograficamente sulla mappa del mondo
# ================================
WORLD_LAYOUT: Dict[int, Dict[str, float]] = {
    # NORTH AMERICA (0-8)
    0:  {"x": 80,  "y": 75},    # Alaska
    1:  {"x": 155, "y": 85},    # Northwest Territory
    2:  {"x": 300, "y": 55},    # Greenland
    3:  {"x": 140, "y": 145},   # Alberta
    4:  {"x": 210, "y": 150},   # Ontario
    5:  {"x": 280, "y": 135},   # Quebec
    6:  {"x": 140, "y": 215},   # Western US
    7:  {"x": 220, "y": 225},   # Eastern US
    8:  {"x": 170, "y": 295},   # Central America

    # SOUTH AMERICA (9-12)
    9:  {"x": 230, "y": 355},   # Venezuela
    10: {"x": 220, "y": 425},   # Peru
    11: {"x": 280, "y": 400},   # Brazil
    12: {"x": 255, "y": 500},   # Argentina

    # EUROPE (13-19)
    13: {"x": 410, "y": 75},    # Iceland
    14: {"x": 420, "y": 140},   # Great Britain
    15: {"x": 480, "y": 80},    # Scandinavia
    16: {"x": 480, "y": 155},   # Northern Europe
    17: {"x": 420, "y": 215},   # Western Europe
    18: {"x": 485, "y": 225},   # Southern Europe
    19: {"x": 560, "y": 120},   # Ukraine

    # AFRICA (20-25)
    20: {"x": 440, "y": 320},   # North Africa
    21: {"x": 520, "y": 305},   # Egypt
    22: {"x": 560, "y": 390},   # East Africa
    23: {"x": 480, "y": 405},   # Congo
    24: {"x": 510, "y": 490},   # South Africa
    25: {"x": 590, "y": 480},   # Madagascar

    # ASIA (26-37)
    26: {"x": 640, "y": 110},   # Ural
    27: {"x": 720, "y": 80},    # Siberia
    28: {"x": 790, "y": 65},    # Yakutsk
    29: {"x": 870, "y": 75},    # Kamchatka
    30: {"x": 780, "y": 130},   # Irkutsk
    31: {"x": 790, "y": 195},   # Mongolia
    32: {"x": 740, "y": 230},   # China
    33: {"x": 870, "y": 185},   # Japan
    34: {"x": 640, "y": 200},   # Afghanistan
    35: {"x": 580, "y": 270},   # Middle East
    36: {"x": 680, "y": 300},   # India
    37: {"x": 750, "y": 310},   # Siam

    # OCEANIA (38-41)
    38: {"x": 775, "y": 400},   # Indonesia
    39: {"x": 860, "y": 380},   # New Guinea
    40: {"x": 810, "y": 490},   # Western Australia
    41: {"x": 890, "y": 470},   # Eastern Australia
}


# Calcola le coordinate SVG per ogni territorio
def territory_coords(n: int) -> Dict[int, Dict[str, float]]:
    coords: Dict[int, Dict[str, float]] = {}
    for t_id in range(n):
        if t_id in WORLD_LAYOUT:
            coords[t_id] = WORLD_LAYOUT[t_id]
        else:
            # Fallback per territori non mappati
            cols = int(math.sqrt(n))
            row = t_id // cols
            col = t_id % cols
            coords[t_id] = {
                "x": 80 + col * 140,
                "y": 80 + row * 140,
            }
    return coords

# Serializza la board per il frontend
def serialize_board(env: RisikoEnvironment, coords: Dict[int, Dict[str, float]]) -> List[Dict[str, Any]]:
    territories = []
    for t_id, t in env.board.territories.items():
        # Recupera nome e continente da world.py
        world_data = TERRITORIES.get(t_id, {})
        territories.append({
            "id": t_id,
            "x": coords[t_id]["x"],
            "y": coords[t_id]["y"],
            "name": world_data.get("name", f"T{t_id}"),
            "continent": world_data.get("continent", "UNKNOWN"),
            "owner": t.owner_id,
            "armies": t.armies,
            "neighbors": list(t.neighbors),
        })
    return territories

# Serializza i continenti per il frontend
def serialize_continents() -> List[Dict[str, Any]]:
    result = []
    for name, data in Config.CONTINENTS.items():
        result.append({
            "name": name,
            "territory_ids": data["t_ids"],
            "bonus": data["bonus"],
        })
    return result

# Formatta la missione in modo leggibile
def format_mission(mission: Dict[str, Any]) -> str:    
    m_type = mission.get("type", "")
    target = mission.get("target", "")
    if m_type == "territory_count":
        return f"Controlla {int(target * 100)}% dei territori"
    if m_type == "continents":
        return f"Conquista: {', '.join(target)}"
    if m_type == "continent_count":
        return f"Controlla {target} continenti a tua scelta"
    return "Sconosciuta"
