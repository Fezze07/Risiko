import math
import os
from typing import Dict, List, Any, Tuple
from config import Config
from core.environment import RisikoEnvironment
from ai.agent import Agent
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


# Calcola le coordinate SVG per ogni territorio su una griglia
def territory_coords(n: int) -> Dict[int, Dict[str, float]]:
    cols = int(math.sqrt(n))
    rows = n // cols
    spacing_x = 140
    spacing_y = 140
    padding = 80
    coords: Dict[int, Dict[str, float]] = {}
    for t_id in range(n):
        row = t_id // cols
        col = t_id % cols
        coords[t_id] = {
            "x": padding + col * spacing_x,
            "y": padding + row * spacing_y,
        }
    return coords

# Serializza la board per il frontend
def serialize_board(env: RisikoEnvironment, coords: Dict[int, Dict[str, float]]) -> List[Dict[str, Any]]:
    territories = []
    for t_id, t in env.board.territories.items():
        territories.append({
            "id": t_id,
            "x": coords[t_id]["x"],
            "y": coords[t_id]["y"],
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
    return "Sconosciuta"
