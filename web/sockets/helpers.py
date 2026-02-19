from typing import Any, Dict

from .constants import MIN_PLAYERS


def fallback_player_colors(total_players: int) -> Dict[int, str]:
    total = max(MIN_PLAYERS, int(total_players))
    return {
        player_id: f"hsl({int((player_id * (360 / total)) % 360)}, 70%, 50%)"
        for player_id in range(1, total + 1)
    }


def normalize_role(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("type")
    if isinstance(value, bool):
        return "HUMAN" if value else "AI"
    role = str(value or "").strip().upper()
    if role in {"H", "HUMAN", "PLAYER"}:
        return "HUMAN"
    return "AI"
