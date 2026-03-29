import random
from typing import Dict, List, Optional
from config import Config
from app.core.territory import Territory
from app.core.world import TERRITORIES

class Board:
    def __init__(self, num_players: Optional[int] = None) -> None:
        self.n: int = Config.GAME["NUM_TERRITORIES"]
        configured_players = int(Config.GAME.get("NUM_PLAYERS", 2))
        resolved_players = num_players if num_players is not None else configured_players
        self.num_players: int = max(2, int(resolved_players))
        self.territories: Dict[int, Territory] = {}
        self._create_map()
        self.reset()

    def _create_map(self) -> None:
        self.territories.clear()
        for t_id, data in TERRITORIES.items():
            territory = Territory(t_id, data["name"])
            territory.neighbors = list(data["neighbors"])
            self.territories[t_id] = territory
        self.n = len(self.territories)

    def _add_neighbor(self, id1: int, id2: int) -> None:
        if id2 not in self.territories[id1].neighbors:
            self.territories[id1].neighbors.append(id2)
        if id1 not in self.territories[id2].neighbors:
            self.territories[id2].neighbors.append(id1)

    def reset(self, num_players: Optional[int] = None) -> None:
        # Resetta la mappa per una nuova partita
        if num_players is not None:
            self.num_players = max(2, int(num_players))
        ids: List[int] = list(self.territories.keys())
        random.shuffle(ids)

        # Reset armate e proprietari
        for i, t_id in enumerate(ids):
            owner: int = (i % self.num_players) + 1
            self.territories[t_id].owner_id = owner
            self.territories[t_id].armies = Config.GAME["STARTING_ARMIES"]

    def get_player_territories(self, player_id: int) -> List[Territory]:
        return [t for t in self.territories.values() if t.owner_id == player_id]
